import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

GlobalRegistrator.register();

afterEach(() => {
  cleanup();
});
