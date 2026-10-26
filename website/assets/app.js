/* Yu Medija Player — yumedija.com
   No dependencies. Two behaviours: mobile menu, copy buttons on install commands. */
(function () {
  "use strict";

  /* ---------- mobile menu ---------- */
  var toggle = document.getElementById("navToggle");
  var nav = document.getElementById("nav");

  function setNav(open) {
    if (!toggle || !nav) return;
    nav.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  }

  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      setNav(!nav.classList.contains("is-open"));
    });

    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) setNav(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setNav(false);
    });

    document.addEventListener("click", function (event) {
      if (!nav.classList.contains("is-open")) return;
      if (nav.contains(event.target) || toggle.contains(event.target)) return;
      setNav(false);
    });
  }

  /* ---------- copy buttons on install commands ---------- */
  var copyTargets = document.querySelectorAll(".install-col pre");

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand("copy") ? resolve() : reject();
      } catch (err) {
        reject(err);
      } finally {
        document.body.removeChild(area);
      }
    });
  }

  Array.prototype.forEach.call(copyTargets, function (pre) {
    var code = pre.querySelector("code");
    if (!code) return;

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-btn";
    btn.textContent = "Copy";
    btn.setAttribute("aria-label", "Copy command");

    btn.addEventListener("click", function () {
      copyText(code.textContent.trim()).then(
        function () {
          btn.textContent = "Copied";
          setTimeout(function () { btn.textContent = "Copy"; }, 1600);
        },
        function () {
          btn.textContent = "Press Ctrl+C";
          setTimeout(function () { btn.textContent = "Copy"; }, 2400);
        }
      );
    });

    pre.appendChild(btn);
  });
})();
