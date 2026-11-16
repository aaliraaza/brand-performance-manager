// Minimal local type shim for react-plotly.js.
// The published @types/react-plotly.js package isn't available in this offline
// environment, so we declare just the surface the app uses. Plotly's own types
// (Data, Layout, Config) ship with plotly.js-dist-min via the `plotly.js` types.
declare module "react-plotly.js" {
  import * as React from "react";
  import type { Data, Layout, Config } from "plotly.js";

  export interface PlotParams {
    data: Data[];
    layout?: Partial<Layout>;
    config?: Partial<Config>;
    style?: React.CSSProperties;
    className?: string;
    useResizeHandler?: boolean;
    onInitialized?: (figure: object, graphDiv: HTMLElement) => void;
    onUpdate?: (figure: object, graphDiv: HTMLElement) => void;
    [key: string]: unknown;
  }

  export default class Plot extends React.Component<PlotParams> {}
}
