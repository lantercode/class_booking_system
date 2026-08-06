<script setup lang="ts">
import { onLaunch, onShow, onHide } from '@dcloudio/uni-app'

onLaunch(() => {
  console.log('App Launch')
})

onShow(() => {
  console.log('App Show')
})

onHide(() => {
  console.log('App Hide')
})
</script>

<style lang="scss">
page {
  background-color: #f5f5f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.container {
  padding: 20rpx;
}

.card {
  background: #ffffff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.06);
}

.text-primary {
  color: #1989fa;
}

.text-gray {
  color: #999999;
}

.text-sm {
  font-size: 26rpx;
}

.text-lg {
  font-size: 32rpx;
}

.text-xl {
  font-size: 36rpx;
}

.flex {
  display: flex;
}

.flex-col {
  flex-direction: column;
}

.items-center {
  align-items: center;
}

.justify-between {
  justify-content: space-between;
}

.gap-20 {
  gap: 20rpx;
}

.mt-20 {
  margin-top: 20rpx;
}

.mb-20 {
  margin-bottom: 20rpx;
}
</style>