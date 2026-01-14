import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getTaxonomy, getAttacks, startEvalRun } from "../api/client";

// Mock global fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

beforeEach(() => {
  mockFetch.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("getTaxonomy", () => {
  it("fetches /api/v1/taxonomy and returns typed data", async () => {
    const mockData = {
      techniques: [
        {
          id: "instruction_override",
          name: "Instruction Override",
          description: "Test",
          example_count: 100,
          difficulty_distribution: { "1": 50, "2": 50 },
        },
      ],
      total_prompts: 1000,
      total_injections: 800,
      total_benign: 200,
      datasets: [],
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockData),
    });

    const result = await getTaxonomy();
    expect(result.total_prompts).toBe(1000);
    expect(result.techniques).toHaveLength(1);
    expect(mockFetch).toHaveBeenCalledWith("/api/v1/taxonomy", {
      headers: { "Content-Type": "application/json" },
    });
  });

  it("throws on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: () => Promise.resolve("Internal Server Error"),
    });

    await expect(getTaxonomy()).rejects.toThrow("API 500");
  });
});

describe("getAttacks", () => {
  it("builds query string from params", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({ attacks: [], total: 0, limit: 20, offset: 0 }),
    });

    await getAttacks({ technique: "roleplay_exploit", limit: 5 });

    const calledUrl = mockFetch.mock.calls[0]![0] as string;
    expect(calledUrl).toContain("technique=roleplay_exploit");
    expect(calledUrl).toContain("limit=5");
  });

  it("omits undefined params", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({ attacks: [], total: 0, limit: 20, offset: 0 }),
    });

    await getAttacks({});

    const calledUrl = mockFetch.mock.calls[0]![0] as string;
    expect(calledUrl).toBe("/api/v1/attacks");
  });
});

describe("startEvalRun", () => {
  it("sends POST with defense config", async () => {
    const mockResponse = {
      eval_run_id: "run-123",
      status: "running",
      total_prompts: 10,
      stream_url: "/api/v1/eval/run/run-123/stream",
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await startEvalRun({
      defense_config: {
        system_prompt: "You are helpful.",
        input_filters: [],
        output_filters: [],
      },
      attack_set: {
        techniques: ["instruction_override"],
        difficulty_range: [1, 5],
        count: 10,
        include_benign: false,
        benign_ratio: 0.3,
      },
    });

    expect(result.eval_run_id).toBe("run-123");

    const [url, init] = mockFetch.mock.calls[0]!;
    expect(url).toBe("/api/v1/eval/run");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toHaveProperty(
      "defense_config.system_prompt",
      "You are helpful.",
    );
  });
});
