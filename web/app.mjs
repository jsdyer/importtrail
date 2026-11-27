import { matches, matchesProduct } from "./model.mjs";

const catalog = document.querySelector("#catalog-filter");
if (catalog) {
  const fields = JSON.parse(document.querySelector("#catalog-fields").textContent);
  const cards = [...document.querySelectorAll("[data-code]")];
  const q = catalog.elements.q, sector = catalog.elements.sector;
  const url = new URL(location.href);
  q.value = url.searchParams.get("q") || "";
  const group = url.searchParams.get("sector");
  if ([...sector.options].some(option => option.value === group)) sector.value = group;
  function filter() {
    let count = 0;
    for (const card of cards) {
      card.hidden = (sector.value && card.dataset.sector !== sector.value) || !matchesProduct(fields[card.dataset.code], q.value);
      if (!card.hidden) count++;
    }
    for (const block of document.querySelectorAll(".group")) block.hidden = !block.querySelector("[data-code]:not([hidden])");
    document.querySelector("#search-status").textContent = count ? count + (count === 1 ? " matching product" : " matching products") : "No matching products in this selection. Try a broader name or clear the filters.";
    const next = new URL(location.href);
    for (const input of [q, sector]) {
      if (input.value.trim()) next.searchParams.set(input.name, input.value.trim());
      else next.searchParams.delete(input.name);
    }
    history.replaceState(null, "", next);
  }
  catalog.hidden = false;
  catalog.addEventListener("input", filter);
  catalog.addEventListener("submit", event => { event.preventDefault(); filter(); });
  catalog.querySelector("button").addEventListener("click", () => { q.value = ""; sector.value = ""; filter(); q.focus(); });
  filter();
}
const nameSearch = document.querySelector("#firms-filter");
if (nameSearch) {
  const input = nameSearch.elements.name;
  const rows = [...document.querySelectorAll("#national tbody tr")];
  nameSearch.hidden = false;
  function filterNames() {
    let count = 0;
    for (const row of rows) {
      row.hidden = !matches(row.textContent, input.value);
      if (!row.hidden) count++;
    }
    document.querySelector("#firms-status").textContent = count + (count === 1 ? " matching entry" : " matching entries");
  }
  input.addEventListener("input", filterNames);
  nameSearch.addEventListener("submit", e => {e.preventDefault(); filterNames();});
  nameSearch.querySelector("button").addEventListener("click", () => {input.value = ""; filterNames(); input.focus();});
}
