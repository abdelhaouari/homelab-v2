import httpx2
import secrets
import time
import argparse
from uuid import UUID
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

from authlib.integrations.httpx_client import OAuth2Client
from authlib.integrations.base_client import OAuthError
from validate_id_token import validate_id_token

ISSUER = "http://localhost:8080/realms/homelab"
CLIENT_ID = "promotion-cli"
REDIRECT_URI = "http://127.0.0.1:8765/callback"


def receive_code(authorization_url: str, expected_state: str) -> str:
    result = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Do not log callback URLs containing authorization codes.
            pass

        def reply(self, status: int, message: str):
            body = message.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path != "/callback":
                self.reply(404, "Not found.")
                return

            parameters = parse_qs(
                parsed.query,
                keep_blank_values=True,
                max_num_fields=20,
            )

            states = parameters.get("state", [])
            if len(states) != 1 or not secrets.compare_digest(
                states[0].encode("utf-8"),
                expected_state.encode("utf-8"),
            ):
                self.reply(400, "Invalid authorization response.")
                return

            if parameters.get("iss") != [ISSUER]:
                result["error"] = "Unexpected authorization response issuer."
                self.reply(400, "Invalid authorization response.")
                return

            if "error" in parameters:
                result["error"] = "Authorization was denied or failed."
                self.reply(400, "Authorization failed. Return to the terminal.")
                return

            codes = parameters.get("code", [])
            if len(codes) != 1 or not codes[0]:
                result["error"] = "Missing or invalid authorization code."
                self.reply(400, "Invalid authorization response.")
                return

            result["code"] = codes[0]
            self.reply(
                200,
                "Authorization response received. Return to the terminal.",
            )

    with HTTPServer(("127.0.0.1", 8765), CallbackHandler) as server:
        server.timeout = 1
        deadline = time.monotonic() + 180

        print("Open this URL in your browser and sign in:")
        print(authorization_url)
        print("\nWaiting up to 180 seconds for the callback...", flush=True)

        while not result and time.monotonic() < deadline:
            server.handle_request()

    if "error" in result:
        raise RuntimeError(result["error"])
    if "code" not in result:
        raise TimeoutError("No valid callback received.")

    return result["code"]


def main():
    parser = argparse.ArgumentParser(
        description="Exercise the local OIDC authorization code flow."
    )

    parser.add_argument(
        "--test-wrong-verifier",
        action="store_true",
        help="Verify that Keycloak rejects an incorrect PKCE verifier.",
    )

    parser.add_argument(
        "--username",
        default="alice-dev",
        help="Username suggested on the Keycloak login page.",
    )
    parser.add_argument(
        "--approve",
        type=UUID,
        metavar="REQUEST_ID",
        help="Approve an existing request instead of creating one.",
    )
    parser.add_argument(
        "--read",
        type=UUID,
        metavar="REQUEST_ID",
        help="Read an existing promotion request.",
    )
    parser.add_argument(
        "--list",
        dest="list_requests",
        action="store_true",
        help="List the 20 most recent promotion requests.",
    )

    args = parser.parse_args()

    if (
        sum(
            (
                args.read is not None,
                args.approve is not None,
                args.list_requests,
            )
        )
        > 1
    ):
        parser.error("Choose only one action: --read, --approve, or --list.")

    code_verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    with OAuth2Client(
        client_id=CLIENT_ID,
        token_endpoint_auth_method="none",
        redirect_uri=REDIRECT_URI,
        scope="openid",
        code_challenge_method="S256",
        timeout=10,
        trust_env=False,
        follow_redirects=False,
    ) as client:
        authorization_url, _ = client.create_authorization_url(
            f"{ISSUER}/protocol/openid-connect/auth",
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
            prompt="login",
            login_hint=args.username,
        )

        code = receive_code(authorization_url, state)

        exchange_verifier = (
            secrets.token_urlsafe(64) if args.test_wrong_verifier else code_verifier
        )

        try:
            token = client.fetch_token(
                f"{ISSUER}/protocol/openid-connect/token",
                grant_type="authorization_code",
                code=code,
                code_verifier=exchange_verifier,
            )
        except OAuthError as error:
            if args.test_wrong_verifier and error.error == "invalid_grant":
                print("Negative PKCE test: PASS")
                print("Keycloak rejected the exchange with invalid_grant.")
                print("No tokens were returned by this exchange.")
                return
            raise

        if args.test_wrong_verifier:
            raise RuntimeError("Negative PKCE test failed: the exchange was accepted.")

        if not token.get("access_token") or not token.get("id_token"):
            raise RuntimeError("Expected tokens were not returned.")

        identity = validate_id_token(
            token["id_token"],
            issuer=ISSUER,
            client_id=CLIENT_ID,
            expected_nonce=nonce,
            access_token=token["access_token"],
        )

        with httpx2.Client(
            timeout=10,
            trust_env=False,
            follow_redirects=False,
        ) as api_client:
            response = api_client.get(
                "http://127.0.0.1:8000/me",
                headers={
                    "Authorization": f"Bearer {token['access_token']}",
                },
            )

        print(f"API /me status: {response.status_code}")
        response.raise_for_status()

        api_identity = response.json()
        if api_identity.get("subject") != identity["sub"]:
            raise RuntimeError("Client and API subjects do not match.")

        print(f"API verified subject: {api_identity['subject']}")
        print(f"API roles: {api_identity['roles']}")

        if args.list_requests:
            with httpx2.Client(
                base_url="http://127.0.0.1:8000",
                headers={
                    "Authorization": f"Bearer {token['access_token']}",
                },
                timeout=10,
                trust_env=False,
                follow_redirects=False,
            ) as api_client:
                list_response = api_client.get(
                    "/promotion-requests",
                    params={"limit": 20, "offset": 0},
                )

            print(f"List requests status: {list_response.status_code}")
            list_response.raise_for_status()
            requests = list_response.json()

            print(f"Requests returned: {len(requests)}")
            for request in requests:
                print(
                    f"{request['id']} | "
                    f"{request['status']} | "
                    f"{request['image_repository']}"
                )
            return

        if args.read is not None:
            with httpx2.Client(
                base_url="http://127.0.0.1:8000",
                headers={
                    "Authorization": f"Bearer {token['access_token']}",
                },
                timeout=10,
                trust_env=False,
                follow_redirects=False,
            ) as api_client:
                read_response = api_client.get(f"/promotion-requests/{args.read}")

            print(f"Read request status: {read_response.status_code}")
            read_response.raise_for_status()
            request = read_response.json()

            print(f"Promotion request ID: {request['id']}")
            print(f"Promotion status: {request['status']}")
            print("Tokens were not displayed or saved.")
            return

        if args.approve is not None:
            with httpx2.Client(
                base_url="http://127.0.0.1:8000",
                headers={
                    "Authorization": f"Bearer {token['access_token']}",
                },
                timeout=10,
                trust_env=False,
                follow_redirects=False,
            ) as api_client:
                decision_response = api_client.post(
                    f"/promotion-requests/{args.approve}/decision",
                    json={"decision": "approved"},
                )
                print(f"Decision status: {decision_response.status_code}")
                decision_response.raise_for_status()
                decided = decision_response.json()

                if decided["status"] != "approved":
                    raise RuntimeError("Unexpected decision status.")
                if decided["decided_by"] != identity["sub"]:
                    raise RuntimeError("Unexpected decision-maker.")
                if decided["requested_by"] == decided["decided_by"]:
                    raise RuntimeError("Self-approval was unexpectedly accepted.")

                stored_response = api_client.get(f"/promotion-requests/{args.approve}")
                stored_response.raise_for_status()
                if stored_response.json() != decided:
                    raise RuntimeError("Stored decision differs from response.")

            print(f"Approved request: {decided['id']}")
            print("Verified decision-maker differs from requester: OK")
            print("Persisted decision retrieved through HTTP: OK")
            print("Tokens were not displayed or saved.")
            return

        with httpx2.Client(
            base_url="http://127.0.0.1:8000",
            headers={
                "Authorization": f"Bearer {token['access_token']}",
            },
            timeout=10,
            trust_env=False,
            follow_redirects=False,
        ) as api_client:
            created_response = api_client.post(
                "/promotion-requests",
                json={
                    "image_repository": "example/promotion-smoke",
                    "image_digest": "sha256:" + "a" * 64,
                    "target": "staging",
                },
            )
            print(f"Create request status: {created_response.status_code}")
            created_response.raise_for_status()
            created = created_response.json()

            if created["requested_by"] != identity["sub"]:
                raise RuntimeError("Unexpected request owner.")
            if created["status"] != "pending":
                raise RuntimeError("Unexpected initial request status.")

            read_response = api_client.get(f"/promotion-requests/{created['id']}")
            print(f"Read request status: {read_response.status_code}")
            read_response.raise_for_status()

            if read_response.json() != created:
                raise RuntimeError("Stored request differs from creation response.")

            print(f"Promotion request ID: {created['id']}")
            print("Authenticated owner and pending status: OK")
            print("Persisted request retrieved through HTTP: OK")

        print("Callback state and issuer: OK")
        print("Authorization code exchanged with PKCE: OK")
        print("ID token signature and claims: OK")
        print(f"Verified issuer: {identity['iss']}")
        print(f"Verified subject: {identity['sub']}")
        print("Tokens were not displayed or saved.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Avoid printing exception details that may contain sensitive data.
        print(f"Login flow failed ({type(error).__name__}).")
        raise SystemExit(1)
