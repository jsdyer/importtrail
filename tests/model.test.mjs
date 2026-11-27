import test from "node:test";
import assert from "node:assert/strict";
import { matches, matchesProduct } from "../web/model.mjs";

test("search matches words within one importer or product, across case and accents", () => {
  const fields = ["Café vert 090111", "Swiss Water Burnaby British Columbia", "Brazil"];
  assert.ok(matchesProduct(fields, "cafe 0901"));
  assert.ok(matchesProduct(fields, "BURNABY swiss"));
  assert.ok(matchesProduct(fields, "Brazil"));
  assert.ok(matchesProduct(fields, ""));
  assert.equal(matchesProduct(fields, "Brazil Burnaby"), false);
  assert.equal(matches("Québec", "<img onerror=alert()>"), false);
});
