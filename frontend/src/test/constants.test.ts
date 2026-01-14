import { describe, expect, it } from "vitest";
import {
  blockRateColor,
  DIFFICULTY_LABELS,
  DATASET_NAMES,
  TECHNIQUE_INFO,
} from "../theme/constants";

describe("blockRateColor", () => {
  it("returns green for rates >= 0.8", () => {
    expect(blockRateColor(0.8)).toBe("green");
    expect(blockRateColor(0.95)).toBe("green");
    expect(blockRateColor(1.0)).toBe("green");
  });

  it("returns orange for rates 0.5-0.79", () => {
    expect(blockRateColor(0.5)).toBe("orange");
    expect(blockRateColor(0.65)).toBe("orange");
    expect(blockRateColor(0.79)).toBe("orange");
  });

  it("returns red for rates < 0.5", () => {
    expect(blockRateColor(0.0)).toBe("red");
    expect(blockRateColor(0.25)).toBe("red");
    expect(blockRateColor(0.49)).toBe("red");
  });
});

describe("TECHNIQUE_INFO", () => {
  it("contains all 11 technique categories", () => {
    expect(Object.keys(TECHNIQUE_INFO)).toHaveLength(11);
  });

  it("includes instruction_override", () => {
    expect(TECHNIQUE_INFO.instruction_override).toBeDefined();
    expect(TECHNIQUE_INFO.instruction_override.name).toBe(
      "Instruction Override",
    );
  });

  it("includes unclassified", () => {
    expect(TECHNIQUE_INFO.unclassified).toBeDefined();
  });

  it("each technique has name, description, and longDescription", () => {
    for (const [id, info] of Object.entries(TECHNIQUE_INFO)) {
      expect(info.name, `${id} missing name`).toBeTruthy();
      expect(info.description, `${id} missing description`).toBeTruthy();
      expect(
        info.longDescription,
        `${id} missing longDescription`,
      ).toBeTruthy();
    }
  });
});

describe("DIFFICULTY_LABELS", () => {
  it("maps levels 1-5", () => {
    expect(DIFFICULTY_LABELS[1]).toBe("Very Easy");
    expect(DIFFICULTY_LABELS[2]).toBe("Easy");
    expect(DIFFICULTY_LABELS[3]).toBe("Medium");
    expect(DIFFICULTY_LABELS[4]).toBe("Hard");
    expect(DIFFICULTY_LABELS[5]).toBe("Very Hard");
  });
});

describe("DATASET_NAMES", () => {
  it("maps all 4 datasets", () => {
    expect(Object.keys(DATASET_NAMES)).toHaveLength(4);
    expect(DATASET_NAMES.deepset).toBe("deepset/prompt-injections");
    expect(DATASET_NAMES.lakera_mosscap).toBe("Lakera/Mosscap CTF");
  });
});
