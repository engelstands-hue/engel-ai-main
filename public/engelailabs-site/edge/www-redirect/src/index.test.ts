import { describe, expect, it } from "vitest";
import worker from "./index";

describe("www canonical redirect", () => {
  it("preserves the path and query on a permanent redirect", () => {
    const response = worker.fetch(new Request("https://www.engelailabs.com/agents?source=profile"));

    expect(response.status).toBe(308);
    expect(response.headers.get("location")).toBe("https://engelailabs.com/agents?source=profile");
    expect(response.headers.get("strict-transport-security")).toContain("includeSubDomains");
  });

  it("fails closed for any unexpected hostname", () => {
    const response = worker.fetch(new Request("https://example.com/"));

    expect(response.status).toBe(421);
    expect(response.headers.get("location")).toBeNull();
  });
});
