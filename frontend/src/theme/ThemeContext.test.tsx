// Behavior tests for theming: choice persists and drives the dark class.

import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ThemeProvider, useTheme } from "./ThemeContext";

function Probe() {
  const { choice, dark, setChoice } = useTheme();
  return (
    <div>
      <p data-testid="state">{`${choice}:${dark}`}</p>
      <button onClick={() => setChoice("light")}>light</button>
      <button onClick={() => setChoice("dark")}>dark</button>
    </div>
  );
}

describe("ThemeProvider", () => {
  it("persists the choice and toggles the dark class", () => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    fireEvent.click(screen.getByText("dark"));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("provena-theme")).toBe("dark");
    fireEvent.click(screen.getByText("light"));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(screen.getByTestId("state")).toHaveTextContent("light:false");
  });
});
