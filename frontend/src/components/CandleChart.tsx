import React from "react";
import { View } from "react-native";
import Svg, { Line, Rect } from "react-native-svg";
import { theme } from "../theme";

type Kline = { open: number; high: number; low: number; close: number };

type Props = {
  klines: Kline[];
  width: number;
  height: number;
};

export default function CandleChart({ klines, width, height }: Props) {
  if (!klines || klines.length === 0) return <View style={{ width, height }} />;
  const padding = 8;
  const innerH = height - padding * 2;
  const innerW = width - padding * 2;
  const lows = klines.map((k) => k.low);
  const highs = klines.map((k) => k.high);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const range = max - min || 1;
  const slot = innerW / klines.length;
  const candleW = Math.max(1, slot * 0.6);

  const yFor = (v: number) => padding + (1 - (v - min) / range) * innerH;

  return (
    <Svg width={width} height={height}>
      {[0.25, 0.5, 0.75].map((p) => (
        <Line
          key={p}
          x1={0}
          x2={width}
          y1={padding + p * innerH}
          y2={padding + p * innerH}
          stroke={theme.colors.border}
          strokeWidth={0.5}
          strokeDasharray="4,4"
        />
      ))}
      {klines.map((k, i) => {
        const x = padding + i * slot + slot / 2;
        const isUp = k.close >= k.open;
        const color = isUp ? theme.colors.buy : theme.colors.sell;
        const yHigh = yFor(k.high);
        const yLow = yFor(k.low);
        const yOpen = yFor(k.open);
        const yClose = yFor(k.close);
        const top = Math.min(yOpen, yClose);
        const bodyH = Math.max(1, Math.abs(yOpen - yClose));
        return (
          <React.Fragment key={i}>
            <Line
              x1={x}
              x2={x}
              y1={yHigh}
              y2={yLow}
              stroke={color}
              strokeWidth={1}
            />
            <Rect
              x={x - candleW / 2}
              y={top}
              width={candleW}
              height={bodyH}
              fill={color}
              rx={1}
            />
          </React.Fragment>
        );
      })}
    </Svg>
  );
}
