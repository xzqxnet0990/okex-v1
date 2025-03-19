module.exports = {
  devServer: {
    client: {
      overlay: {
        warnings: false,
        errors: true,
        runtimeErrors: (error) => {
          if (error.message && error.message.includes('ResizeObserver')) {
            return false;
          }
          return true;
        }
      }
    }
  },
  configureWebpack: {
    performance: {
      hints: false
    }
  }
} 