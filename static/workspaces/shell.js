// Workspace shell scripts.

// Render Lucide icons.
lucide.createIcons();

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
    preventItemDefault: true,
});
