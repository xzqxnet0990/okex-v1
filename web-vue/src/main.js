import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import store from './store'

// 更彻底地处理ResizeObserver错误
const originalError = window.console.error;
window.console.error = (...args) => {
  if (
    args.length > 0 && 
    typeof args[0] === 'string' && 
    (args[0].includes('ResizeObserver loop') || 
     args[0].includes('ResizeObserver Loop'))
  ) {
    // 忽略ResizeObserver循环错误
    return;
  }
  originalError.apply(window.console, args);
};

// 全局错误处理
window.addEventListener('error', (event) => {
  if (event.message && 
     (event.message.includes('ResizeObserver loop') || 
      event.message.includes('ResizeObserver Loop'))) {
    event.stopImmediatePropagation();
    event.preventDefault();
    return false;
  }
}, true);

// 修补ResizeObserver以防止循环错误
const patchResizeObserver = () => {
  const ResizeObserver = window.ResizeObserver;
  if (!ResizeObserver) return;
  
  // 保存原始的ResizeObserver
  const OriginalResizeObserver = ResizeObserver;
  
  // 创建一个新的ResizeObserver类
  window.ResizeObserver = function(...args) {
    const ro = new OriginalResizeObserver(...args);
    
    // 重写observe方法
    const originalObserve = ro.observe;
    ro.observe = function(...innerArgs) {
      try {
        return originalObserve.apply(this, innerArgs);
      } catch (e) {
        if (e.message && e.message.includes('ResizeObserver loop')) {
          // 忽略循环错误
          return null;
        }
        throw e;
      }
    };
    
    return ro;
  };
  
  // 复制原型和静态属性
  window.ResizeObserver.prototype = OriginalResizeObserver.prototype;
  Object.keys(OriginalResizeObserver).forEach(key => {
    window.ResizeObserver[key] = OriginalResizeObserver[key];
  });
};

// 在DOM加载完成后应用补丁
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', patchResizeObserver);
} else {
  patchResizeObserver();
}

const app = createApp(App)
app.use(ElementPlus)
app.use(store)
app.mount('#app') 