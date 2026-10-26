export function createRequestForm(apiRequest, onCreated) {
  const form = document.createElement("form");

  // This template contains only static application markup.
  form.innerHTML = `
    <h3>New promotion request</h3>
    <p>
      <label>
        Image repository
        <input name="repository" required maxlength="255"
               placeholder="example/my-app" />
      </label>
    </p>
    <p>
      <label>
        Image digest
        <input name="digest" required
               minlength="71" maxlength="71"
               pattern="sha256:[0-9a-f]{64}"
               placeholder="sha256:..." />
      </label>
    </p>
    <p>Target: staging</p>
    <button type="submit">Create request</button>
    <p role="status"></p>
  `;

  const submit = form.querySelector("button");
  const message = form.querySelector('[role="status"]');

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submit.disabled) return;

    const data = new FormData(form);
    submit.disabled = true;
    message.textContent = "Creating request...";

    let request;
    try {
      request = await apiRequest("/promotion-requests", {
        method: "POST",
        body: {
          image_repository: data.get("repository"),
          image_digest: data.get("digest"),
          target: "staging",
        },
      });
    } catch (error) {
      message.textContent = error.message;
      submit.disabled = false;
      return;
    }

    form.reset();
    message.textContent = `Request created: ${request.id}`;

    try {
      await onCreated(request.id);
    } catch {
      message.textContent =
        `Request created: ${request.id}. Reload to refresh the list.`;
    } finally {
      submit.disabled = false;
    }
  });

  return form;
}

export function createDecisionControls(apiRequest, requestId, onDecided) {
  const container = document.createElement("div");
  const message = document.createElement("p");
  message.setAttribute("role", "status");

  const buttons = [];

  for (const [label, decision] of [
    ["Approve", "approved"],
    ["Reject", "rejected"],
  ]) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    buttons.push(button);
    container.append(button);

    button.addEventListener("click", async () => {
      if (button.disabled) return;
      buttons.forEach((item) => { item.disabled = true; });
      message.textContent = "Saving decision...";

      try {
        await apiRequest(
          `/promotion-requests/${encodeURIComponent(requestId)}/decision`,
          {
            method: "POST",
            body: { decision },
          },
        );
      } catch (error) {
        message.textContent = error.message;
        buttons.forEach((item) => { item.disabled = false; });
        return;
      }

      message.textContent = "Decision saved.";

      try {
        await onDecided(requestId);
      } catch {
        message.textContent = "Decision saved. Reload to refresh the request.";
      }
    });
  }

  container.append(message);
  return container;
}
