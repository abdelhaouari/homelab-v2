import {
  createRequestForm,
  createDecisionControls,
} from "./actions.js";

export async function mountRequests(apiRequest, actor) {
  const section = document.createElement("section");
  const heading = document.createElement("h2");
  heading.textContent = "Promotion requests";

  const message = document.createElement("p");
  message.setAttribute("role", "status");

  const list = document.createElement("ul");
  const previous = document.createElement("button");
  previous.textContent = "Previous";
  previous.type = "button";

  const next = document.createElement("button");
  next.textContent = "Next";
  next.type = "button";

  const detail = document.createElement("section");
  section.append(heading, message, list, previous, next, detail);
  document.querySelector("main").append(section);

  const limit = 20;
  let offset = 0;
  let selectedId = null;

  async function showDetail(id) {
    selectedId = id;
    detail.textContent = "Loading request...";

    try {
      const request = await apiRequest(
        `/promotion-requests/${encodeURIComponent(id)}`,
      );
      if (selectedId !== id) return;

      const title = document.createElement("h3");
      title.textContent = "Request details";

      const fields = document.createElement("dl");
      const values = [
        ["ID", request.id],
        ["Repository", request.image_repository],
        ["Digest", request.image_digest],
        ["Target", request.target],
        ["Status", request.status],
        ["Requested by", request.requested_by],
        ["Created at", request.created_at],
        ["Decided by", request.decided_by],
        ["Decided at", request.decided_at],
      ];

      for (const [label, value] of values) {
        const term = document.createElement("dt");
        const description = document.createElement("dd");
        term.textContent = label;
        description.textContent = value ?? "Not decided";
        fields.append(term, description);
      }

      detail.replaceChildren(title, fields);

      const canDecide =
        actor.roles.includes("approver") &&
        request.status === "pending" &&
        request.requested_by !== actor.subject;

      if (canDecide) {
        detail.append(
          createDecisionControls(apiRequest, request.id, async (id) => {
            await loadPage(offset);
            await showDetail(id);
          }),
        );
      }
    } catch (error) {
      if (selectedId === id) {
        detail.textContent = error.message;
      }
    }
  }

  async function loadPage(targetOffset) {
    previous.disabled = true;
    next.disabled = true;
    selectedId = null;
    detail.replaceChildren();
    list.replaceChildren();
    message.textContent = "Loading requests...";

    try {
      const requests = await apiRequest(
        `/promotion-requests?limit=${limit}&offset=${targetOffset}`,
      );
      offset = targetOffset;

      for (const request of requests) {
        const item = document.createElement("li");
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = `${request.image_repository} | ${request.status} | ${request.id}`;
        button.addEventListener("click", () => showDetail(request.id));
        item.append(button);
        list.append(item);
      }

      message.textContent = requests.length
        ? `Page ${offset / limit + 1}: ${requests.length} request(s).`
        : "No requests on this page.";

      previous.disabled = offset === 0;
      next.disabled = requests.length < limit;
    } catch (error) {
      message.textContent = error.message;
      previous.disabled = offset === 0;
    }
  }

  previous.addEventListener("click", () => loadPage(offset - limit));
  next.addEventListener("click", () => loadPage(offset + limit));

  if (actor.roles.includes("developer")) {
    const form = createRequestForm(apiRequest, async (id) => {
      await loadPage(0);
      await showDetail(id);
    });
    section.insertBefore(form, message);
  }

  await loadPage(0);
}
