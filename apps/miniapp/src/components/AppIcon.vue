<template>
  <view class="icon-wrapper" :style="wrapperStyle">
    <image
      class="icon-image"
      :src="iconSrc"
      :style="imageStyle"
      mode="aspectFit"
    />
  </view>
</template>

<script setup lang="ts">
import { iconSvgMap } from "@/static/icons/icon-map";
import { computed } from "vue";

interface Props {
  name: keyof typeof iconSvgMap;
  size?: number;
  color?: string;
  strokeWidth?: number;
}

const props = withDefaults(defineProps<Props>(), {
  size: 24,
  color: "#8b7355",
  strokeWidth: 1.5,
});

const iconSrc = computed(() => {
  const svgContent = iconSvgMap[props.name];
  if (!svgContent) return "";

  // 替换 currentColor 为实际颜色
  const colorizedSvg = svgContent.replace(/currentColor/g, props.color);
  const encodedSvg = encodeURIComponent(colorizedSvg);

  return `data:image/svg+xml;charset=utf-8,${encodedSvg}`;
});

const wrapperStyle = computed(() => ({
  width: `${props.size}rpx`,
  height: `${props.size}rpx`,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
}));

const imageStyle = computed(() => ({
  width: `${props.size}rpx`,
  height: `${props.size}rpx`,
}));
</script>

<style lang="scss" scoped>
.icon-wrapper {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-image {
  width: 100%;
  height: 100%;
}
</style>
