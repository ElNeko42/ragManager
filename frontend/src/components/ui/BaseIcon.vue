<script setup lang="ts">
import { computed } from 'vue'

/**
 * The drawing of every icon the panel uses, as path data on a 24 by 24 grid.
 *
 * They are kept here rather than as files so that a request never goes out for
 * one: an icon that arrives late leaves a hole in a button that is already on
 * screen. They are drawn as strokes in the current colour, which is what lets
 * the same folder sit on a white sidebar and on a cyan selected row without a
 * second copy in another shade.
 */
const PATHS: Record<string, string[]> = {
  folder: ['M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z'],
  folderOpen: [
    'M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V11H3Z',
    'M3 11h18l-1.6 6.2A2 2 0 0 1 17.5 19h-11a2 2 0 0 1-1.9-1.4Z'
  ],
  file: ['M6 3h7l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z', 'M13 3v5h5'],
  chevronRight: ['m9 5 7 7-7 7'],
  chevronDown: ['m5 9 7 7 7-7'],
  plus: ['M12 5v14', 'M5 12h14'],
  search: ['M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z', 'm16.5 16.5 4 4'],
  upload: ['M12 16V4', 'm7 9 5-5 5 5', 'M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3'],
  download: ['M12 4v12', 'm7 11 5 5 5-5', 'M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3'],
  pencil: ['M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17Z', 'm14 6 4 4'],
  trash: ['M4 7h16', 'M9 7V4h6v3', 'M6 7l1 13h10l1-13', 'M10 11v6', 'M14 11v6'],
  shield: ['M12 3l8 3v6c0 4.4-3.2 7.7-8 9-4.8-1.3-8-4.6-8-9V6Z'],
  robot: [
    'M7 9h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2Z',
    'M12 5v4',
    'M9.5 13.5h.01',
    'M14.5 13.5h.01'
  ],
  layers: ['m12 3 9 5-9 5-9-5Z', 'm3 13 9 5 9-5', 'm3 17 9 4 9-4'],
  pulse: ['M3 12h4l3 7 4-14 3 7h4'],
  gear: [
    'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
    'M19.4 14.5a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1v.3a2 2 0 1 1-4 0v-.2a1.6 1.6 0 0 0-2.8-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H3a2 2 0 1 1 0-4h.2a1.6 1.6 0 0 0 1.1-2.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 2.7-1.1V3a2 2 0 1 1 4 0v.2a1.6 1.6 0 0 0 2.8 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7h.3a2 2 0 1 1 0 4h-.2a1.6 1.6 0 0 0-1.5 1.1Z'
  ],
  key: ['M15 4a5 5 0 1 0-4.6 7L9 12.4l-1 1-2 .3-.3 2-1 1-1.7-1.7 7-7A5 5 0 0 0 15 4Z', 'M16 8h.01'],
  mail: ['M4 6h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Z', 'm4 8 8 5 8-5'],
  sun: ['M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z', 'M12 2v2', 'M12 20v2', 'M4 12H2', 'M22 12h-2', 'm5 5 1.5 1.5', 'm17.5 17.5 1.5 1.5', 'm19 5-1.5 1.5', 'm6.5 17.5-1.5 1.5'],
  moon: ['M20 14.5A8.5 8.5 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z'],
  monitor: ['M4 5h16a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z', 'M9 20h6', 'M12 16v4'],
  logout: ['M15 4h3a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-3', 'M10 8 6 12l4 4', 'M6 12h9'],
  menu: ['M4 7h16', 'M4 12h16', 'M4 17h16'],
  close: ['m6 6 12 12', 'm18 6-12 12'],
  check: ['m5 12 5 5L20 7'],
  copy: ['M9 9h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1Z', 'M5 15H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v1'],
  move: ['M5 8V6a1 1 0 0 1 1-1h5l2 2.5h5a1 1 0 0 1 1 1V17a1 1 0 0 1-1 1H9', 'm7 12-3 3 3 3', 'M4 15h8'],
  link: [
    'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7L11.3 7',
    'M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7L12.7 17'
  ]
}

const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 18 })

const paths = computed(() => PATHS[props.name] ?? [])
</script>

<template>
  <svg
    class="icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="(path, index) in paths" :key="index" :d="path" />
  </svg>
</template>

<style scoped>
.icon {
  flex: none;
  display: block;
}
</style>
