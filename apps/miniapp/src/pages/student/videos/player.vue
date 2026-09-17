<template>
  <view class="video-player-page">
    <AppNavbar :title="title" />
    <view class="player-container">
      <video
        :src="videoUrl"
        class="video-player"
        controls
        autoplay
        object-fit="contain"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
import AppNavbar from "@/components/AppNavbar.vue";
import { onMounted, ref } from "vue";

const title = ref("视频播放");
const videoUrl = ref("");

onMounted(() => {
  const pages = getCurrentPages();
  const currentPage = pages[pages.length - 1] as any;
  const options = currentPage.options || {};
  title.value = decodeURIComponent(options.title || "视频播放");
  videoUrl.value = decodeURIComponent(options.url || "");
});
</script>

<style lang="scss" scoped>
.video-player-page {
  min-height: 100vh;
  background-color: #000;
}

.player-container {
  width: 100%;
  height: calc(100vh - var(--navbar-height));
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #000;
}

.video-player {
  width: 100%;
  height: 100%;
}
</style>
