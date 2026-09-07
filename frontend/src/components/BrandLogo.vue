<template>
  <div class="brand" :class="[`size-${size}`, { breathe }]" :aria-label="'PornWeb'">
    <svg class="mark" viewBox="0 0 32 32" aria-hidden="true">
      <!-- Distinctive PW media mark: rounded frame + play + web node (not PH orange-box wordmark) -->
      <defs>
        <linearGradient id="pwMarkGrad" x1="4" y1="4" x2="28" y2="28" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#ffc266"/>
          <stop offset="55%" stop-color="#ffa31a"/>
          <stop offset="100%" stop-color="#e07a00"/>
        </linearGradient>
      </defs>
      <rect x="1.5" y="1.5" width="29" height="29" rx="8" fill="#151515" stroke="url(#pwMarkGrad)" stroke-width="1.6"/>
      <path d="M12.2 9.6v12.8l11-6.4-11-6.4z" fill="url(#pwMarkGrad)"/>
      <circle cx="23.2" cy="9.2" r="2.35" fill="none" stroke="url(#pwMarkGrad)" stroke-width="1.35"/>
      <path d="M23.2 6.85v4.7M20.85 9.2h4.7" stroke="url(#pwMarkGrad)" stroke-width="1.15" stroke-linecap="round"/>
    </svg>
    <span class="wordmark">
      <span class="w-porn">Porn</span><span class="w-web">Web</span>
    </span>
  </div>
</template>

<script setup>
defineProps({
  size: { type: String, default: 'md' }, // sm | md | lg
  breathe: { type: Boolean, default: false },
})
</script>

<style scoped>
.brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  line-height: 1;
  user-select: none;
}
.mark {
  flex-shrink: 0;
  display: block;
}
.wordmark {
  display: inline-flex;
  align-items: baseline;
  font-weight: 800;
  letter-spacing: -0.03em;
}
.w-porn { color: #f5f5f5; }
.w-web {
  color: var(--accent, #ffa31a);
  font-weight: 900;
  position: relative;
}
/* Accent underline instead of orange filled box — avoids PH clone */
.w-web::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -2px;
  height: 2px;
  border-radius: 1px;
  background: linear-gradient(90deg, var(--accent, #ffa31a), transparent 95%);
  opacity: 0.85;
}

.size-sm .mark { width: 22px; height: 22px; }
.size-sm .wordmark { font-size: 18px; }
.size-sm { gap: 7px; }

.size-md .mark { width: 26px; height: 26px; }
.size-md .wordmark { font-size: 20px; }

.size-lg .mark { width: 40px; height: 40px; }
.size-lg .wordmark { font-size: 32px; }
.size-lg { gap: 12px; }
.size-lg .w-web::after { bottom: -3px; height: 2.5px; }

.breathe .mark {
  animation: logo-breathe 3.6s ease-in-out infinite;
  transform-origin: center;
}
@keyframes logo-breathe {
  0%, 100% { transform: scale(1); filter: drop-shadow(0 0 0 rgba(255,163,26,0)); }
  50% { transform: scale(1.045); filter: drop-shadow(0 0 8px rgba(255,163,26,0.35)); }
}
@media (prefers-reduced-motion: reduce) {
  .breathe .mark { animation: none; }
}
</style>
