(() => {
  const header = document.querySelector("[data-site-header]");
  const toggle = document.querySelector("[data-menu-toggle]");
  const navigation = document.querySelector("[data-navigation]");

  function setMenu(open) {
    if (!toggle || !navigation) return;
    toggle.setAttribute("aria-expanded", String(open));
    navigation.classList.toggle("open", open);
    document.body.classList.toggle("menu-open", open);
  }

  toggle?.addEventListener("click", () => {
    setMenu(toggle.getAttribute("aria-expanded") !== "true");
  });

  navigation?.addEventListener("click", (event) => {
    if (event.target.closest("a")) setMenu(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setMenu(false);
  });

  window.addEventListener(
    "scroll",
    () => header?.classList.toggle("scrolled", window.scrollY > 12),
    { passive: true },
  );

  const sections = [...document.querySelectorAll("main section[id]")];
  const sectionLinks = [...document.querySelectorAll(".site-nav [data-section]")];
  if (!sections.length || !sectionLinks.length) return;

  const activate = (id) => {
    sectionLinks.forEach((link) => {
      const active = link.dataset.section === id;
      link.classList.toggle("active", active);
      if (active) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  };

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) activate(visible.target.id);
    },
    { rootMargin: "-20% 0px -65%", threshold: [0, 0.15, 0.4] },
  );
  sections.forEach((section) => observer.observe(section));
})();
