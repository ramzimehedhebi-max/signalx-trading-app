import React from "react";
import { View } from "react-native";
import Svg, { Path, Defs, LinearGradient, Stop } from "react-native-svg";
import { theme } from "../theme";

type Props = {
  data: number[];
  width?: number;
  height?: number;
  positive?: boolean;
};

export default function MiniChart({ data, width = 120, height = 40, positive }: Props) {
  if (!data || data.length < 2) return <View style={{ width, height }} />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const points = data.map((v, i) => {
    const x = i * stepX;
    const y = height - ((v - min) / range) * height;
    return [x, y];
  });

  const path =
    "M " +
    points
      .map(([x, y], i) => (i === 0 ? `${x},${y}` : `L ${x},${y}`))
      .join(" ");

  const areaPath = `${path} L ${width},${height} L 0,${height} Z`;

  const isPositive = positive ?? data[data.length - 1] >= data[0];
  const color = isPositive ? theme.colors.buy : theme.colors.sell;
  const gradId = `g-${isPositive ? "p" : "n"}`;

  return (
    <Svg width={width} height={height}>
      <Defs>
        <LinearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={color} stopOpacity="0.35" />
          <Stop offset="1" stopColor={color} stopOpacity="0" />
        </LinearGradient>
      </Defs>
      <Path d={areaPath} fill={`url(#${gradId})`} />
      <Path d={path} stroke={color} strokeWidth={1.8} fill="none" />
    </Svg>
  );
}
