// strip empty comments from codeblocks
const observer = new MutationObserver(() => {
  document.querySelectorAll("code > span.c1").forEach((el) => {
    if (el.childNodes && el.childNodes[0].textContent === "# ") {
      el.childNodes[0].textContent = "";
    }
  });
});

observer.observe(document.body, { subtree: true, childList: true });
