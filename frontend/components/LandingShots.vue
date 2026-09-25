<template>
  <div class="shot-story">
    <figure class="shot-card reveal">
      <div class="shot-frame">
        <div class="shot-bar"><i /><i /><i /></div>
        <img src="/images/workflow2.png" :alt="t('landing.shots.chainAlt')" width="1920" height="908" loading="lazy" />
      </div>
      <figcaption>
        <span class="shot-step">{{ t('landing.shots.chainStep') }}</span>
        <strong>{{ t('landing.shots.chainTitle') }}</strong>
        <p>{{ t('landing.shots.chainText') }}</p>
      </figcaption>
    </figure>

    <div class="shot-split">
      <figure class="shot-card reveal">
        <div class="shot-frame">
          <div class="shot-bar"><i /><i /><i /></div>
          <img src="/images/workflow_run.png" :alt="t('landing.shots.runAlt')" width="1600" height="900" loading="lazy" />
        </div>
        <figcaption>
          <span class="shot-step">{{ t('landing.shots.runStep') }}</span>
          <strong>{{ t('landing.shots.runTitle') }}</strong>
          <p>{{ t('landing.shots.runText') }}</p>
        </figcaption>
      </figure>
      <figure class="shot-card is-phone reveal">
        <div class="shot-phone">
          <img src="/images/tg.png" :alt="t('landing.shots.tgAlt')" width="720" height="1280" loading="lazy" />
        </div>
        <figcaption>
          <span class="shot-step">{{ t('landing.shots.tgStep') }}</span>
          <strong>{{ t('landing.shots.tgTitle') }}</strong>
          <p>{{ t('landing.shots.tgText') }}</p>
        </figcaption>
      </figure>
    </div>
  </div>
</template>

<script setup lang="ts">
const { t } = useI18n()
</script>
