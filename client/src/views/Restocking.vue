<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <!-- Budget Slider -->
      <div class="budget-control">
        <label class="budget-label" for="budget-slider">
          {{ t('restocking.budgetLabel') }}
          <span class="budget-value">{{ formatCurrency(budget, currentCurrency) }}</span>
        </label>
        <input
          id="budget-slider"
          type="range"
          min="0"
          :max="maxBudget"
          :step="500"
          v-model.number="budget"
          class="budget-slider"
        />
        <div class="budget-range-info">
          <span>{{ formatCurrency(0, currentCurrency) }}</span>
          <span>{{ formatCurrency(maxBudget, currentCurrency) }}</span>
        </div>
      </div>

      <!-- Stats Cards -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.stats.budget') }}</div>
          <div class="stat-value">{{ formatCurrency(budget, currentCurrency) }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.stats.orderTotal') }}</div>
          <div class="stat-value">{{ formatCurrency(recommendedItemsTotal, currentCurrency) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.stats.remaining') }}</div>
          <div class="stat-value">{{ formatCurrency(remainingBudget, currentCurrency) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.stats.leadTime') }}</div>
          <div class="stat-value">{{ t('restocking.days', { days: recommendedLeadTime }) }}</div>
        </div>
      </div>

      <!-- Recommended Items Table -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }}</h3>
        </div>
        <div class="table-container">
          <table class="restocking-table">
            <thead>
              <tr>
                <th class="col-item">{{ t('restocking.table.item') }}</th>
                <th class="col-sku">{{ t('restocking.table.sku') }}</th>
                <th class="col-trend">{{ t('restocking.table.trend') }}</th>
                <th class="col-qty">{{ t('restocking.table.qty') }}</th>
                <th class="col-unit-cost">{{ t('restocking.table.unitCost') }}</th>
                <th class="col-total">{{ t('restocking.table.lineTotal') }}</th>
                <th class="col-lead-time">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommendedItems" :key="item.sku">
                <td class="col-item">{{ translateProductName(item.name) }}</td>
                <td class="col-sku">{{ item.sku }}</td>
                <td class="col-trend">
                  <span :class="['badge', getTrendBadgeClass(item.trend)]">
                    {{ t(`trends.${item.trend}`) }}
                  </span>
                </td>
                <td class="col-qty">
                  {{ item.quantity }}
                  <span v-if="item.partialFill" class="partial-note">{{ t('restocking.ofTotal', { total: item.suggestedQty }) }}</span>
                </td>
                <td class="col-unit-cost">{{ formatCurrency(item.unit_cost, currentCurrency) }}</td>
                <td class="col-total">{{ formatCurrency(item.lineTotal, currentCurrency) }}</td>
                <td class="col-lead-time">{{ t('restocking.days', { days: item.lead_time_days }) }}</td>
              </tr>
              <tr v-if="recommendedItems.length === 0">
                <td colspan="7" class="no-data">
                  {{ t('restocking.noRecommendedItems') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Not Included Items -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.notIncluded') }}</h3>
        </div>
        <div class="table-container">
          <table class="restocking-table">
            <thead>
              <tr>
                <th class="col-item">{{ t('restocking.table.item') }}</th>
                <th class="col-sku">{{ t('restocking.table.sku') }}</th>
                <th class="col-reason">{{ t('restocking.table.reason') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in notIncludedItems" :key="item.sku">
                <td class="col-item">{{ translateProductName(item.name) }}</td>
                <td class="col-sku">{{ item.sku }}</td>
                <td class="col-reason">{{ t(`restocking.reasons.${item.reason}`, { total: item.suggestedQty }) }}</td>
              </tr>
              <tr v-if="notIncludedItems.length === 0">
                <td colspan="3" class="no-data">
                  {{ t('restocking.allItemsIncluded') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Place Order Button -->
      <div class="actions">
        <button
          @click="placeOrder"
          :disabled="recommendedItems.length === 0 || submitting"
          class="btn btn-primary place-order-btn"
        >
          <span v-if="submitting">{{ t('restocking.submitting') }}</span>
          <span v-else>{{ t('restocking.placeOrder') }}</span>
        </button>
        <div v-if="submitSuccess" class="success-message">
          {{ t('restocking.successMessage', { orderNumber: submitSuccess.order_number }) }}
          <router-link to="/orders" class="link">
            {{ t('restocking.viewOrders') }}
          </router-link>
        </div>
        <div v-if="submitError" class="error-message">
          {{ submitError }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])

    const budget = ref(10000)
    const submitting = ref(false)
    const submitSuccess = ref(null)
    const submitError = ref(null)

    const loadData = async () => {
      try {
        loading.value = true
        const data = await api.getDemandForecasts()
        forecasts.value = data
      } catch (err) {
        error.value = 'Failed to load demand forecasts: ' + err.message
      } finally {
        loading.value = false
      }
    }

    // Calculate max budget as the total cost of all eligible items at suggested quantities
    const maxBudget = computed(() => {
      const eligibleItems = forecasts.value.filter(item => item.trend !== 'decreasing')

      const totalCost = eligibleItems.reduce((sum, item) => {
        let suggestedQty = 0

        if (item.trend === 'increasing') {
          suggestedQty = Math.max(0, item.forecasted_demand - item.current_demand)
        } else if (item.trend === 'stable') {
          suggestedQty = item.forecasted_demand
        }

        const itemCost = suggestedQty * item.unit_cost
        return sum + itemCost
      }, 0)

      // Round up to the next 5000
      return Math.ceil(totalCost / 5000) * 5000 || 5000
    })

    // Compute recommended and not included items
    const computedRecommendations = computed(() => {
      // Initialize all items with additional calculated fields
      const augmentedItems = forecasts.value.map(item => {
        // Calculate suggested quantity based on trend
        let suggestedQty = 0
        if (item.trend === 'increasing') {
          suggestedQty = Math.max(0, item.forecasted_demand - item.current_demand)
        } else if (item.trend === 'stable') {
          suggestedQty = item.forecasted_demand
        }

        // Preview only - mirrors LEAD_TIME_DAYS in server/main.py, which is authoritative
        let leadTime = 7 // default
        if (item.trend === 'increasing') leadTime = 10
        else if (item.trend === 'decreasing') leadTime = 14

        return {
          ...item,
          suggestedQty,
          lead_time_days: leadTime,
          included: false,
          quantity: 0,
          lineTotal: 0,
          reason: null,
          partialFill: false
        }
      })

      // Rank items according to business rules:
      // 1. Increasing items first, sorted by % growth ((forecasted-current)/current) descending
      // 2. Then stable items by forecasted_demand descending
      const rankedItems = [...augmentedItems].sort((a, b) => {
        // First prioritize by trend: increasing before stable
        if (a.trend === 'increasing' && b.trend !== 'increasing') return -1
        if (b.trend === 'increasing' && a.trend !== 'increasing') return 1

        // Within increasing items, sort by % growth descending
        if (a.trend === 'increasing' && b.trend === 'increasing') {
          const growthA = a.current_demand > 0 ? (a.forecasted_demand - a.current_demand) / a.current_demand : 0
          const growthB = b.current_demand > 0 ? (b.forecasted_demand - b.current_demand) / b.current_demand : 0
          return growthB - growthA
        }

        // Within stable items, sort by forecasted_demand descending
        if (a.trend === 'stable' && b.trend === 'stable') {
          return b.forecasted_demand - a.forecasted_demand
        }

        return 0
      })

      // Greedy allocation: take each ranked item in full while it fits, then partially fill
      // the first item that doesn't and stop, so lower-priority items never jump the queue
      const recommended = []
      const notIncluded = []
      let remainingBudget = budget.value

      for (const item of rankedItems) {
        // Exclude decreasing trend items
        if (item.trend === 'decreasing') {
          item.reason = 'decliningDemand'
          notIncluded.push(item)
          continue
        }

        // Skip items with zero suggested quantity
        if (item.suggestedQty <= 0) {
          item.reason = 'noDemandGap'
          notIncluded.push(item)
          continue
        }

        // Calculate cost to include this item
        const itemCost = item.suggestedQty * item.unit_cost

        if (itemCost <= remainingBudget) {
          // Can afford full quantity
          item.quantity = item.suggestedQty
          item.lineTotal = itemCost
          item.included = true
          recommended.push(item)
          remainingBudget -= itemCost
        } else {
          // Try partial fill
          const affordableQty = Math.floor(remainingBudget / item.unit_cost)
          if (affordableQty >= 1) {
            // Partial fill possible
            item.quantity = affordableQty
            item.lineTotal = affordableQty * item.unit_cost
            item.included = true
            item.partialFill = true
            recommended.push(item)
            remainingBudget -= item.lineTotal
          } else {
            // Cannot afford even one unit
            item.reason = 'overBudget'
            notIncluded.push(item)
          }

          // Stop processing further items since we're at/below budget
          break
        }
      }

      // Mark remaining items as not included due to budget
      const processedItems = [...recommended, ...notIncluded]
      const unprocessedItems = rankedItems.filter(item => !processedItems.includes(item))
      unprocessedItems.forEach(item => {
        if (!item.reason) {
          item.reason = 'overBudget'
        }
        notIncluded.push(item)
      })

      return { recommended, notIncluded, remainingBudget }
    })

    const recommendedItems = computed(() => computedRecommendations.value.recommended)
    const notIncludedItems = computed(() => computedRecommendations.value.notIncluded)

    const recommendedItemsTotal = computed(() => {
      return recommendedItems.value.reduce((sum, item) => sum + item.lineTotal, 0)
    })

    const remainingBudget = computed(() => {
      return budget.value - recommendedItemsTotal.value
    })

    const recommendedLeadTime = computed(() => {
      if (recommendedItems.value.length === 0) return 0
      return Math.max(...recommendedItems.value.map(item => item.lead_time_days))
    })

    const getTrendBadgeClass = (trend) => {
      const trendMap = {
        'increasing': 'warning',
        'stable': 'info',
        'decreasing': 'danger'
      }
      return trendMap[trend] || 'info'
    }

    const placeOrder = async () => {
      try {
        submitting.value = true
        submitError.value = null
        submitSuccess.value = null

        const orderData = {
          budget: budget.value,
          items: recommendedItems.value.map(item => ({
            sku: item.item_sku,
            name: item.item_name,
            quantity: item.quantity,
            unit_cost: item.unit_cost,
            trend: item.trend
          }))
        }

        const result = await api.createRestockingOrder(orderData)
        submitSuccess.value = result
      } catch (err) {
        submitError.value = err.response?.data?.detail || err.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadData)

    return {
      t,
      loading,
      error,
      budget,
      maxBudget,
      recommendedItems,
      notIncludedItems,
      recommendedItemsTotal,
      remainingBudget,
      recommendedLeadTime,
      submitting,
      submitSuccess,
      submitError,
      currentCurrency,
      formatCurrency,
      translateProductName,
      getTrendBadgeClass,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-control {
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
}

.budget-label {
  display: block;
  font-weight: 500;
  margin-bottom: 1rem;
  color: #0f172a;
}

.budget-value {
  margin-left: 0.5rem;
  font-weight: 600;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: #e2e8f0;
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.budget-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
  border: none;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.budget-range-info {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
  font-size: 0.875rem;
  color: #64748b;
}

.restocking-table {
  table-layout: fixed;
  width: 100%;
}

.col-item {
  width: 200px;
}

.col-sku {
  width: 100px;
}

.col-trend {
  width: 100px;
}

.col-qty {
  width: 100px;
}

.col-unit-cost {
  width: 100px;
}

.col-total {
  width: 100px;
}

.col-lead-time {
  width: 100px;
}

.col-reason {
  width: 250px;
}

/* Tabular numerals for number columns */
.col-qty,
.col-unit-cost,
.col-total,
.col-lead-time {
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.actions {
  margin-top: 2rem;
  text-align: center;
}

.place-order-btn {
  padding: 0.75rem 2rem;
  font-size: 1rem;
  font-weight: 500;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background-color: #3b82f6;
  color: white;
  border: none;
}

.btn-primary:hover:not(:disabled) {
  background-color: #2563eb;
}

.btn-primary:disabled {
  background-color: #94a3b8;
  cursor: not-allowed;
}

.success-message {
  margin-top: 1rem;
  padding: 1rem;
  background-color: #dcfce7;
  color: #166534;
  border-radius: 6px;
  border: 1px solid #bbf7d0;
}

.error-message {
  margin-top: 1rem;
  padding: 1rem;
  background-color: #fee2e2;
  color: #991b1b;
  border-radius: 6px;
  border: 1px solid #fecaca;
}

.link {
  margin-left: 0.5rem;
  color: #3b82f6;
  text-decoration: underline;
}

.partial-note {
  display: block;
  font-size: 0.75rem;
  color: #64748b;
}

.no-data {
  text-align: center;
  color: #64748b;
  font-style: italic;
  padding: 2rem;
}
</style>