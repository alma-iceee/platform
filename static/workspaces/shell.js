// Workspace shell scripts.

// Render Lucide icons.
lucide.createIcons();

// Workspace selector dropdown.
(function () {
    const menu = document.querySelector("[data-workspace-menu]");
    if (!menu) {
        return;
    }

    const trigger = menu.querySelector("[data-workspace-trigger]");
    const dropdown = menu.querySelector("[data-workspace-dropdown]");
    if (!trigger || !dropdown) {
        return;
    }

    const openMenu = () => {
        menu.classList.add("is-open");
        trigger.setAttribute("aria-expanded", "true");
    };

    const closeMenu = () => {
        menu.classList.remove("is-open");
        trigger.setAttribute("aria-expanded", "false");
    };

    trigger.addEventListener("click", function (event) {
        if (menu.classList.contains("is-open")) {
            closeMenu();
            return;
        }

        openMenu();
    });

    dropdown.addEventListener("click", function (event) {
        const item = event.target.closest(".topbar-workspace-menu-item");
        if (item) {
            closeMenu();
        }
    });

    document.addEventListener("click", function (event) {
        if (!menu.contains(event.target)) {
            closeMenu();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeMenu();
        }
    });
}());

// Profile menu dropdown.
(function () {
    const menu = document.querySelector("[data-profile-menu]");
    if (!menu) {
        return;
    }

    const trigger = menu.querySelector("[data-profile-trigger]");
    const dropdown = menu.querySelector("[data-profile-dropdown]");
    if (!trigger || !dropdown) {
        return;
    }

    const openMenu = () => {
        menu.classList.add("is-open");
        dropdown.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
    };

    const closeMenu = () => {
        menu.classList.remove("is-open");
        dropdown.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
    };

    trigger.addEventListener("click", function (event) {
        event.stopPropagation();

        if (menu.classList.contains("is-open")) {
            closeMenu();
            return;
        }

        openMenu();
    });

    dropdown.addEventListener("click", function (event) {
        const item = event.target.closest("[role='menuitem']");
        if (item) {
            event.preventDefault();
            closeMenu();
        }
    });

    document.addEventListener("click", function (event) {
        if (!menu.contains(event.target)) {
            closeMenu();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeMenu();
        }
    });
}());
