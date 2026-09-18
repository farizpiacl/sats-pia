document.addEventListener("DOMContentLoaded", function () {
  /* ---------------- Sidebar toggle (mobile) ---------------- */
  var toggleBtn = document.getElementById("sidebarToggleBtn");
  var sidebar = document.getElementById("appSidebar");
  var backdrop = document.getElementById("sidebarBackdrop");

  function closeSidebar() {
    sidebar && sidebar.classList.remove("show");
    backdrop && backdrop.classList.remove("show");
  }

  if (toggleBtn && sidebar && backdrop) {
    toggleBtn.addEventListener("click", function () {
      sidebar.classList.toggle("show");
      backdrop.classList.toggle("show");
    });
    backdrop.addEventListener("click", closeSidebar);
  }

  /* ---------------- Auto-dismiss toasts ---------------- */
  document.querySelectorAll(".toast").forEach(function (toastEl) {
    if (window.bootstrap && bootstrap.Toast) {
      var toast = new bootstrap.Toast(toastEl, { delay: 5000 });
      toast.show();
    }
  });

  /* ---------------- Confirm dialogs for destructive actions ---------------- */
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("submit", function (e) {
      var msg = el.getAttribute("data-confirm") || "Are you sure?";
      if (!window.confirm(msg)) {
        e.preventDefault();
      }
    });
  });

  /* ---------------- Auto-submit filter forms on select change ---------------- */
  document.querySelectorAll("[data-auto-submit]").forEach(function (el) {
    el.addEventListener("change", function () {
      el.closest("form").submit();
    });
  });

  /* ---------------- Enable Bootstrap tooltips ---------------- */
  if (window.bootstrap && bootstrap.Tooltip) {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
      new bootstrap.Tooltip(el);
    });
  }
});
