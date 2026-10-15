const taskList = document.querySelector("#task-list");
const taskDialog = document.querySelector("#task-dialog");
const taskForm = document.querySelector("#task-form");
const toast = document.querySelector("#toast");
let tasks = [];
let currentFilter = "all";
let toastTimer;

const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[char]));

function localDate(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function dateLabel(value) {
  if (!value) return "No due date";
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const today = localDate(new Date());
  const difference = Math.round((date - today) / 86400000);
  if (difference === 0) return "Due today";
  if (difference === 1) return "Due tomorrow";
  return `Due ${new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date)}`;
}

function isDueSoon(task) {
  if (!task.due_date || task.completed) return false;
  const [year, month, day] = task.due_date.split("-").map(Number);
  const due = new Date(year, month - 1, day);
  const today = localDate(new Date());
  const nextWeek = new Date(today);
  nextWeek.setDate(today.getDate() + 7);
  return due >= today && due <= nextWeek;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 2600);
}

function updateSummary() {
  const active = tasks.filter((task) => !task.completed);
  const completed = tasks.length - active.length;
  const today = localDate(new Date());
  const nextWeek = new Date(today);
  nextWeek.setDate(today.getDate() + 7);
  const dueSoon = active.filter((task) => {
    if (!task.due_date) return false;
    const [year, month, day] = task.due_date.split("-").map(Number);
    const due = new Date(year, month - 1, day);
    return due >= today && due <= nextWeek;
  }).length;

  document.querySelector("#total-count").textContent = tasks.length;
  document.querySelector("#due-count").textContent = dueSoon;
  document.querySelector("#done-count").textContent = completed;
  document.querySelector("#nav-count").textContent = active.length;
  document.querySelector("#heading-count").textContent = tasks.length;
  document.querySelector("#all-filter-count").textContent = tasks.length;
  document.querySelector("#done-note").textContent = tasks.length
    ? `${Math.round((completed / tasks.length) * 100)}% of your list` : "one step at a time";
  document.querySelector("#progress-bar").style.width = tasks.length
    ? `${(completed / tasks.length) * 100}%` : "0%";

  const courses = [...new Set(tasks.map((task) => task.course).filter(Boolean))].sort();
  document.querySelector("#course-list").innerHTML = courses.length
    ? courses.map((course, index) => `<div class="course-item"><i class="course-dot dot-${index % 5}"></i><span>${escapeHtml(course)}</span><small>${tasks.filter((task) => task.course === course && !task.completed).length}</small></div>`).join("")
    : '<div class="course-empty">Your courses will show here</div>';
}

function renderTasks() {
  const query = document.querySelector("#search-input").value.trim().toLowerCase();
  const visible = tasks.filter((task) => {
    const matchesFilter = currentFilter === "all"
      || (currentFilter === "active" && !task.completed)
      || (currentFilter === "completed" && task.completed)
      || (currentFilter === "due" && isDueSoon(task));
    const matchesQuery = `${task.title} ${task.course}`.toLowerCase().includes(query);
    return matchesFilter && matchesQuery;
  });

  if (!visible.length) {
    const isEmpty = tasks.length === 0;
    taskList.innerHTML = `<div class="empty-state"><div class="empty-art"><span>✳</span><i></i></div><h3>${isEmpty ? "A fresh page." : "Nothing here right now."}</h3><p>${isEmpty ? "Add your first assignment and give future-you a head start." : "Try another filter or add a new task to your list."}</p>${isEmpty ? '<button class="primary-button empty-add" type="button">＋ Add your first task</button>' : ""}</div>`;
    return;
  }

  const today = localDate(new Date());
  taskList.innerHTML = visible.map((task) => {
    const overdue = !task.completed && task.due_date && (() => {
      const [year, month, day] = task.due_date.split("-").map(Number);
      return new Date(year, month - 1, day) < today;
    })();
    const dueClass = overdue ? " due-overdue" : "";
    return `<article class="task-row${task.completed ? " is-complete" : ""}" data-id="${task.id}">
      <button class="task-check" type="button" data-action="toggle" aria-label="${task.completed ? "Mark incomplete" : "Mark complete"}" aria-pressed="${task.completed}">${task.completed ? "✓" : ""}</button>
      <div class="task-main"><div class="task-title-line"><h3>${escapeHtml(task.title)}</h3><span class="priority priority-${task.priority}"><i></i>${task.priority}</span></div><div class="task-meta">${task.course ? `<span class="course-tag">${escapeHtml(task.course)}</span><span class="meta-separator">·</span>` : ""}<span class="due-label${dueClass}">${escapeHtml(dateLabel(task.due_date))}${overdue ? " · overdue" : ""}</span></div></div>
      <button class="delete-task" type="button" data-action="delete" aria-label="Delete ${escapeHtml(task.title)}" title="Delete task">×</button>
    </article>`;
  }).join("");
}

async function loadTasks() {
  taskList.innerHTML = '<div class="loading-state"><span class="loader"></span>Loading your tasks…</div>';
  try {
    const response = await fetch("/api/tasks", { cache: "no-store" });
    if (!response.ok) throw new Error("Could not load tasks");
    tasks = await response.json();
    updateSummary();
    renderTasks();
  } catch (_error) {
    taskList.innerHTML = '<div class="empty-state"><h3>Could not load your tasks.</h3><p>Check your connection and refresh the page.</p></div>';
  }
}

function openForm() {
  taskForm.reset();
  document.querySelector("#form-error").textContent = "";
  taskDialog.showModal();
  window.setTimeout(() => document.querySelector("#task-title").focus(), 50);
}

document.querySelector("#today-label").textContent = new Intl.DateTimeFormat(undefined, {
  weekday: "short", month: "short", day: "numeric",
}).format(new Date());
const hour = new Date().getHours();
document.querySelector("#greeting").textContent = hour < 12 ? "A GOOD MORNING TO YOU" : hour < 18 ? "A GOOD AFTERNOON TO YOU" : "A GOOD EVENING TO YOU";

document.querySelector("#open-form").addEventListener("click", openForm);
document.querySelector("#course-shortcut").addEventListener("click", openForm);
document.querySelector("#close-form").addEventListener("click", () => taskDialog.close());
document.querySelector("#cancel-form").addEventListener("click", () => taskDialog.close());
document.querySelector("#search-input").addEventListener("input", renderTasks);
document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => {
  currentFilter = button.dataset.filter;
  document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item === button));
  renderTasks();
}));

document.querySelector('[data-shortcut="today"]').addEventListener("click", (event) => {
  event.preventDefault();
  currentFilter = "due";
  document.querySelectorAll(".filter").forEach((button) => button.classList.remove("active"));
  renderTasks();
});

taskForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(taskForm);
  const payload = Object.fromEntries(formData.entries());
  const submitButton = taskForm.querySelector('[type="submit"]');
  submitButton.disabled = true;
  document.querySelector("#form-error").textContent = "";
  try {
    const response = await fetch("/api/tasks", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not save the task.");
    taskDialog.close();
    showToast("Task added to your list");
    await loadTasks();
  } catch (error) {
    document.querySelector("#form-error").textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

taskList.addEventListener("click", async (event) => {
  if (event.target.closest(".empty-add")) return openForm();
  const actionButton = event.target.closest("[data-action]");
  if (!actionButton) return;
  const row = actionButton.closest("[data-id]");
  if (!row) return;
  const task = tasks.find((item) => item.id === Number(row.dataset.id));
  if (!task) return;
  try {
    if (actionButton.dataset.action === "toggle") {
      const response = await fetch(`/api/tasks/${task.id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ completed: !task.completed }),
      });
      if (!response.ok) throw new Error("Could not update task");
      showToast(task.completed ? "Task moved back to your list" : "Nice work — task completed!");
    } else if (actionButton.dataset.action === "delete") {
      const response = await fetch(`/api/tasks/${task.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Could not delete task");
      showToast("Task removed");
    }
    await loadTasks();
  } catch (error) {
    showToast(error.message);
  }
});

loadTasks();
