import { computed, ref } from 'vue'
import type { ComputedRef, Ref } from 'vue'

export interface TreeNode {
  id: string
  parent: string | null
}

export interface TreeRow<T extends TreeNode> {
  node: T
  depth: number
  hasChildren: boolean
  collapsed: boolean
}

export interface TreeOptions<T extends TreeNode> {
  keep?: (node: T) => boolean
  expandAll?: () => boolean
}

/**
 * Flattens a parent-linked list into indented rows that fold.
 *
 * Both trees in the panel walk the same shape, so the walking, the folding and
 * the depth live here once. Children are indexed by parent before the walk:
 * asking the whole list for the children of every node turns drawing a tree
 * into work that grows with the square of its size.
 *
 * Takes the nodes, an optional filter and an optional override that opens every
 * branch, which a search needs so that folds cannot bury a hit. Returns the
 * rows to draw and the folding action.
 */
export function useTree<T extends TreeNode>(
  nodes: Ref<T[]> | ComputedRef<T[]>,
  options: TreeOptions<T> = {}
) {
  const collapsed = ref<Record<string, boolean>>({})

  const byParent = computed(() => {
    const index = new Map<string | null, T[]>()
    for (const node of nodes.value) {
      const siblings = index.get(node.parent)
      if (siblings) {
        siblings.push(node)
      } else {
        index.set(node.parent, [node])
      }
    }
    return index
  })

  /**
   * Reports whether a node or anything below it survives the filter.
   */
  function branchKept(node: T): boolean {
    if (!options.keep || options.keep(node)) {
      return true
    }
    return (byParent.value.get(node.id) ?? []).some(branchKept)
  }

  const rows = computed<TreeRow<T>[]>(() => {
    const open = options.expandAll?.() === true
    const out: TreeRow<T>[] = []
    const walk = (parent: string | null, depth: number) => {
      for (const node of byParent.value.get(parent) ?? []) {
        if (options.keep && !branchKept(node)) {
          continue
        }
        const children = byParent.value.get(node.id) ?? []
        const shut = !open && collapsed.value[node.id] === true
        out.push({ node, depth, hasChildren: children.length > 0, collapsed: shut })
        if (!shut) {
          walk(node.id, depth + 1)
        }
      }
    }
    walk(null, 0)
    return out
  })

  /**
   * Folds or unfolds one branch.
   */
  function fold(id: string): void {
    collapsed.value = { ...collapsed.value, [id]: !collapsed.value[id] }
  }

  return { rows, fold }
}
