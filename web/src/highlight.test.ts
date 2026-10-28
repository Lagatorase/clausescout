import { pieces, step, visitOrder } from "./highlight";
import type { Finding } from "./types";

const f = (category: string, start: number, end: number): Finding => ({
  category, start, end, text: "", score: 1, location: "", high_stakes: false,
});

test("overlapping findings split the text into covered pieces", () => {
  const out = pieces(10, [f("A", 2, 6), f("B", 4, 8)]);
  expect(out.map((p) => [p.start, p.end, p.covers])).toEqual([
    [0, 2, []], [2, 4, [0]], [4, 6, [0, 1]], [6, 8, [1]], [8, 10, []],
  ]);
});

test("visit order follows clause type order, then position", () => {
  const list = [f("B", 1, 2), f("A", 9, 10), f("A", 3, 4)];
  expect(visitOrder(list, ["A", "B"])).toEqual([2, 1, 0]);
});

test("step wraps around and starts from either end", () => {
  expect(step(-1, 3, 1)).toBe(0);
  expect(step(-1, 3, -1)).toBe(2);
  expect(step(2, 3, 1)).toBe(0);
  expect(step(0, 0, 1)).toBe(-1);
});
