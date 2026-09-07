<script setup lang="ts">
import { onMounted, ref } from 'vue'

interface ServiceStatus {
  healthy: boolean
  detail: string | null
}

interface HealthReport {
  healthy: boolean
  services: Record<string, ServiceStatus>
}

const report = ref<HealthReport | null>(null)
const error = ref<string | null>(null)

/**
 * Fetches the backend health report and stores it for rendering.
 *
 * Accepts the 503 response as a valid report, since a degraded stack still
 * describes which service is down.
 */
async function loadHealth() {
  error.value = null
  try {
    const response = await fetch('/health/')
    report.value = (await response.json()) as HealthReport
  } catch (cause) {
    report.value = null
    error.value = String(cause)
  }
}

onMounted(loadHealth)
</script>

<template>
  <main>
    <h1>ragManager</h1>
    <p>Self-hosted RAG storage with an MCP server for external agents.</p>

    <section>
      <h2>Stack health</h2>
      <p v-if="error" class="down">{{ error }}</p>
      <ul v-else-if="report">
        <li v-for="(status, name) in report.services" :key="name">
          <span :class="status.healthy ? 'up' : 'down'">{{ status.healthy ? 'up' : 'down' }}</span>
          {{ name }}
          <em v-if="status.detail">{{ status.detail }}</em>
        </li>
      </ul>
      <p v-else>Loading…</p>
      <button type="button" @click="loadHealth">Refresh</button>
    </section>
  </main>
</template>

<style scoped>
main {
  font-family: system-ui, sans-serif;
  max-width: 40rem;
  margin: 3rem auto;
  padding: 0 1rem;
  line-height: 1.5;
}
ul {
  list-style: none;
  padding: 0;
}
li {
  padding: 0.25rem 0;
}
.up {
  color: #15803d;
  font-weight: 600;
}
.down {
  color: #b91c1c;
  font-weight: 600;
}
em {
  color: #6b7280;
  display: block;
  font-size: 0.85rem;
}
</style>
