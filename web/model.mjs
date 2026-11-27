export function normalize(value) {
  return String(value).normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

export function matches(value, query) {
  const text = normalize(value);
  return normalize(query).trim().split(/\s+/).every(token => text.includes(token));
}

export function matchesProduct(fields, query) {
  return fields.some(field => matches(field, query));
}
