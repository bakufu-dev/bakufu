import { describe, expect, it } from "vitest";
import { VERSION } from "./index";

describe("frontend skeleton", () => {
  it("exposes a version constant", () => {
    expect(VERSION).toBe("0.0.0");
  });
});
