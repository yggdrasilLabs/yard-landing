// Tabbed examples: choosing a tab activates the same tab in every group with
// the same name, and the choice is remembered per group in this browser.
(function () {
    function activateTab(group, name) {
        document.querySelectorAll('.tabs[data-tabs="' + group + '"]').forEach(function (tabs) {
            if (!tabs.querySelector('[data-tab="' + name + '"]')) { return; }
            tabs.querySelectorAll("[data-tab]").forEach(function (el) {
                var on = el.getAttribute("data-tab") === name;
                el.classList.toggle("active", on);
                if (el.getAttribute("role") === "tab") {
                    el.setAttribute("aria-selected", on ? "true" : "false");
                }
            });
        });
    }

    function initTabs() {
        document.querySelectorAll(".tabs .tab").forEach(function (button) {
            button.addEventListener("click", function () {
                var group = button.closest(".tabs").getAttribute("data-tabs");
                var name = button.getAttribute("data-tab");
                activateTab(group, name);
                try { localStorage.setItem("tabs:" + group, name); } catch (e) {}
            });
        });
        document.querySelectorAll(".tabs[data-tabs]").forEach(function (tabs) {
            var group = tabs.getAttribute("data-tabs");
            var saved = null;
            try { saved = localStorage.getItem("tabs:" + group); } catch (e) {}
            if (saved) { activateTab(group, saved); }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initTabs);
    } else {
        initTabs();
    }
})();
