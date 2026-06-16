// Workspace shell scripts.

// Render Lucide icons.
lucide.createIcons();

// Collapsible primary sidebar (icons only ↔ icons + labels), persisted.
// The expanded class is set on <html> by an inline head script before first
// paint (no flash); here we just wire the toggle and keep aria in sync.
(function () {
    const root = document.documentElement;
    const toggle = document.querySelector("[data-sidebar-toggle]");
    if (!toggle) {
        return;
    }

    const STORAGE_KEY = "ordo:sidebar-expanded";

    const syncAria = () => {
        toggle.setAttribute("aria-expanded", root.classList.contains("sidebar-expanded") ? "true" : "false");
    };

    syncAria();

    toggle.addEventListener("click", function () {
        const expanded = root.classList.toggle("sidebar-expanded");
        localStorage.setItem(STORAGE_KEY, expanded ? "1" : "0");
        syncAria();
    });
}());

// Generic modals: open via [data-modal-open="<id>"], close via [data-modal-close],
// backdrop click, or Escape. Overlay element needs id and class "modal-overlay".
(function () {
    const open = (overlay) => {
        overlay.classList.add("is-open");
        document.body.style.overflow = "hidden";
    };
    const close = (overlay) => {
        overlay.classList.remove("is-open");
        document.body.style.overflow = "";
    };

    document.addEventListener("click", function (event) {
        const trigger = event.target.closest("[data-modal-open]");
        if (trigger) {
            const overlay = document.getElementById(trigger.getAttribute("data-modal-open"));
            if (overlay) {
                event.preventDefault();
                open(overlay);
                return;
            }
        }

        if (event.target.closest("[data-modal-close]")) {
            const overlay = event.target.closest(".modal-overlay");
            if (overlay) {
                close(overlay);
            }
            return;
        }

        if (event.target.classList.contains("modal-overlay")) {
            close(event.target);
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            document.querySelectorAll(".modal-overlay.is-open").forEach(close);
        }
    });
}());

// Generic dropdown: toggled by a trigger, closed on outside click, Escape,
// or selecting an item. `toggleHidden` also flips the [hidden] attribute on
// the list; `preventItemDefault` is for menus whose items are buttons, not
// navigation links.
function initDropdown({ menu, trigger, dropdown, item, toggleHidden = false, preventItemDefault = false }) {
    const menuEl = document.querySelector(menu);
    if (!menuEl) {
        return;
    }

    const triggerEl = menuEl.querySelector(trigger);
    const dropdownEl = menuEl.querySelector(dropdown);
    if (!triggerEl || !dropdownEl) {
        return;
    }

    const openMenu = () => {
        menuEl.classList.add("is-open");
        if (toggleHidden) {
            dropdownEl.hidden = false;
        }
        triggerEl.setAttribute("aria-expanded", "true");
    };

    const closeMenu = () => {
        menuEl.classList.remove("is-open");
        if (toggleHidden) {
            dropdownEl.hidden = true;
        }
        triggerEl.setAttribute("aria-expanded", "false");
    };

    triggerEl.addEventListener("click", function (event) {
        event.stopPropagation();
        if (menuEl.classList.contains("is-open")) {
            closeMenu();
            return;
        }

        openMenu();
    });

    dropdownEl.addEventListener("click", function (event) {
        if (event.target.closest(item)) {
            if (preventItemDefault) {
                event.preventDefault();
            }
            closeMenu();
        }
    });

    document.addEventListener("click", function (event) {
        if (!menuEl.contains(event.target)) {
            closeMenu();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeMenu();
        }
    });
}

initDropdown({
    menu: "[data-workspace-menu]",
    trigger: "[data-workspace-trigger]",
    dropdown: "[data-workspace-dropdown]",
    item: ".topbar-workspace-menu-item",
});

initDropdown({
    menu: "[data-profile-menu]",
    trigger: "[data-profile-trigger]",
    dropdown: "[data-profile-dropdown]",
    item: "[role='menuitem']",
    toggleHidden: true,
});
