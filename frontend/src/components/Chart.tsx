import Plot from "react-plotly.js";
import type { Data, Layout } from "plotly.js";
import type { ChartSpec } from "../lib/api";

const NAVY = "#003087";
const ORANGE = "#E87722";

const baseLayout: Partial<Layout> = {
  height: 340,
  margin: { l: 60, r: 24, t: 36, b: 48 },
  paper_bgcolor: "#FFFFFF",
  plot_bgcolor: "#FFFFFF",
  font: { family: "Inter, sans-serif", color: "#16213e", size: 12 },
  showlegend: false,
};

const config = { displayModeBar: false, responsive: true };

/** Render a ChartSpec produced by the backend's deterministic chart_data(). */
export function SpecChart({ spec }: { spec: ChartSpec }) {
  let data: Data[];

  if (spec.kind === "line") {
    data = [
      {
        x: spec.x as number[],
        y: spec.y as number[],
        type: "scatter",
        mode: "lines+markers",
        line: { color: spec.color ?? NAVY, width: 2.5 },
        marker: { color: spec.color ?? NAVY, size: 6 },
      },
    ];
  } else {
    const horizontal = spec.orientation === "h";
    data = [
      {
        x: spec.x as number[],
        y: spec.y as string[],
        type: "bar",
        orientation: horizontal ? "h" : "v",
        marker: { color: spec.colors ?? spec.color ?? ORANGE },
        text: (spec.x as number[]).map((v) => `${v > 0 ? "+" : ""}${v}`),
        textposition: "outside",
      } as Data,
    ];
  }

  const layout: Partial<Layout> = {
    ...baseLayout,
    title: { text: spec.title, font: { size: 14, color: NAVY } },
    xaxis: { title: { text: spec.xTitle } },
    yaxis: { title: { text: spec.yTitle }, automargin: true },
  };

  if (spec.threshold != null) {
    layout.shapes = [
      {
        type: "line",
        x0: spec.threshold,
        x1: spec.threshold,
        yref: "paper",
        y0: 0,
        y1: 1,
        line: { color: "red", dash: "dash", width: 1.5 },
      },
    ];
    layout.annotations = [
      {
        x: spec.threshold,
        yref: "paper",
        y: 1,
        text: `${spec.threshold}% threshold`,
        showarrow: false,
        font: { size: 10, color: "red" },
        xanchor: "left",
      },
    ];
  }

  return <Plot data={data} layout={layout} config={config} style={{ width: "100%" }} useResizeHandler />;
}

/** Convenience: a multi-series line chart (used by the dashboard top-brands trend). */
export function MultiLineChart({
  series,
  title,
  xTitle,
  yTitle,
}: {
  series: { name: string; x: (string | number)[]; y: number[] }[];
  title?: string;
  xTitle?: string;
  yTitle?: string;
}) {
  const palette = [NAVY, ORANGE, "#4f6db5", "#1a8f5b", "#9b59b6"];
  const data: Data[] = series.map((s, i) => ({
    x: s.x,
    y: s.y,
    type: "scatter",
    mode: "lines+markers",
    name: s.name,
    line: { color: palette[i % palette.length], width: 2.5 },
    marker: { size: 5 },
  }));
  const layout: Partial<Layout> = {
    ...baseLayout,
    showlegend: true,
    legend: { orientation: "h", yanchor: "bottom", y: 1.04, x: 0 },
    title: title ? { text: title, font: { size: 14, color: NAVY } } : undefined,
    xaxis: { title: { text: xTitle ?? "" } },
    yaxis: { title: { text: yTitle ?? "" }, automargin: true },
  };
  return <Plot data={data} layout={layout} config={config} style={{ width: "100%" }} useResizeHandler />;
}

/** Convenience: a horizontal bar chart. */
export function HBarChart({
  labels,
  values,
  colors,
  title,
  xTitle,
  textFmt,
  threshold,
}: {
  labels: string[];
  values: number[];
  colors?: string[];
  title?: string;
  xTitle?: string;
  textFmt?: (v: number) => string;
  threshold?: number;
}) {
  const data: Data[] = [
    {
      x: values,
      y: labels,
      type: "bar",
      orientation: "h",
      marker: { color: colors ?? ORANGE },
      text: textFmt ? values.map(textFmt) : undefined,
      textposition: "outside",
    } as Data,
  ];
  const layout: Partial<Layout> = {
    ...baseLayout,
    title: title ? { text: title, font: { size: 14, color: NAVY } } : undefined,
    xaxis: { title: { text: xTitle ?? "" } },
    yaxis: { automargin: true },
  };
  if (threshold != null) {
    layout.shapes = [
      {
        type: "line",
        x0: threshold,
        x1: threshold,
        yref: "paper",
        y0: 0,
        y1: 1,
        line: { color: "red", dash: "dash", width: 1.5 },
      },
    ];
  }
  return <Plot data={data} layout={layout} config={config} style={{ width: "100%" }} useResizeHandler />;
}
