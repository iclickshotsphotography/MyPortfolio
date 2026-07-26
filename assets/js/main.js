(() => {
  const navToggle = document.querySelector(".nav-toggle");
  const navLinks = document.querySelector(".nav-links");

  const closeMenu = () => {
    if (!navToggle || !navLinks) return;
    navLinks.classList.remove("is-open");
    navToggle.classList.remove("is-open");
    navToggle.setAttribute("aria-expanded", "false");
    navToggle.setAttribute("aria-label", "Open navigation");
  };

  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => {
      const open = navLinks.classList.toggle("is-open");
      navToggle.classList.toggle("is-open", open);
      navToggle.setAttribute("aria-expanded", String(open));
      navToggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    });
    navLinks.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
    window.addEventListener("resize", () => { if (window.innerWidth > 820) closeMenu(); });
  }

  document.querySelectorAll("[data-year]").forEach((element) => {
    element.textContent = new Date().getFullYear();
  });

  const photoLinks = [...document.querySelectorAll(".photo")];
  if (!photoLinks.length) return;

  const lightbox = document.createElement("div");
  lightbox.className = "lightbox";
  lightbox.setAttribute("role", "dialog");
  lightbox.setAttribute("aria-modal", "true");
  lightbox.setAttribute("aria-label", "Full-screen photograph viewer");
  lightbox.setAttribute("aria-hidden", "true");
  lightbox.innerHTML = `
    <button class="lightbox-close" type="button" aria-label="Close image viewer">&times;</button>
    <button class="lightbox-prev" type="button" aria-label="Previous image">&lsaquo;</button>
    <figure class="lightbox-figure"><img alt=""><figcaption class="lightbox-count" aria-live="polite"></figcaption></figure>
    <button class="lightbox-next" type="button" aria-label="Next image">&rsaquo;</button>
  `;
  document.body.appendChild(lightbox);

  const image = lightbox.querySelector("img");
  const count = lightbox.querySelector(".lightbox-count");
  const closeButton = lightbox.querySelector(".lightbox-close");
  const previousButton = lightbox.querySelector(".lightbox-prev");
  const nextButton = lightbox.querySelector(".lightbox-next");
  const controls = [closeButton, previousButton, nextButton];
  let currentIndex = 0;
  let previouslyFocused = null;
  let touchStartX = null;

  const showImage = (index) => {
    currentIndex = (index + photoLinks.length) % photoLinks.length;
    const link = photoLinks[currentIndex];
    const thumbnail = link.querySelector("img");
    image.src = link.dataset.full || link.href;
    image.alt = thumbnail.alt;
    count.textContent = `${currentIndex + 1} / ${photoLinks.length}`;
  };

  const openLightbox = (index) => {
    previouslyFocused = document.activeElement;
    showImage(index);
    lightbox.classList.add("is-visible");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.classList.add("lightbox-open");
    closeButton.focus();
  };

  const closeLightbox = () => {
    lightbox.classList.remove("is-visible");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.classList.remove("lightbox-open");
    image.removeAttribute("src");
    if (previouslyFocused) previouslyFocused.focus();
  };

  photoLinks.forEach((link, index) => link.addEventListener("click", (event) => {
    event.preventDefault();
    openLightbox(index);
  }));
  closeButton.addEventListener("click", closeLightbox);
  previousButton.addEventListener("click", () => showImage(currentIndex - 1));
  nextButton.addEventListener("click", () => showImage(currentIndex + 1));
  lightbox.addEventListener("click", (event) => { if (event.target === lightbox) closeLightbox(); });
  lightbox.addEventListener("touchstart", (event) => { touchStartX = event.changedTouches[0].clientX; }, { passive: true });
  lightbox.addEventListener("touchend", (event) => {
    if (touchStartX === null) return;
    const distance = event.changedTouches[0].clientX - touchStartX;
    if (Math.abs(distance) > 45) showImage(currentIndex + (distance < 0 ? 1 : -1));
    touchStartX = null;
  }, { passive: true });

  document.addEventListener("keydown", (event) => {
    if (!lightbox.classList.contains("is-visible")) return;
    if (event.key === "Escape") closeLightbox();
    else if (event.key === "ArrowLeft") showImage(currentIndex - 1);
    else if (event.key === "ArrowRight") showImage(currentIndex + 1);
    else if (event.key === "Tab") {
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });
})();
