/**
 * analytics-charts.js
 * Chart.js controller for Analytics & Reporting Dashboard.
 * Reads metrics cleanly from the decoupled #chartDataPayload JSON script island.
 */

(function() {
  'use strict';

  document.addEventListener('DOMContentLoaded', function() {
    var payloadEl = document.getElementById('chartDataPayload');
    if (!payloadEl) return;

    var chartData = {};
    try {
      chartData = JSON.parse(payloadEl.textContent || '{}');
    } catch(e) {
      console.error('Failed to parse chartDataPayload JSON:', e);
      return;
    }

    var dailyData = chartData.dailySubmissions || [];
    var statusData = chartData.statusBreakdown || [];
    var monthlyData = chartData.monthlySubmissions || [];
    var byFormData = chartData.byForm || [];

    // Palette matching enterprise design system
    var STATUS_COLORS = {
      submitted: '#0284c7',
      pending_approval: '#f59e0b',
      approved: '#10b981',
      rejected: '#f43f5e',
      withdrawn: '#94a3b8'
    };

    var defaultFont = {
      family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      size: 11
    };

    var chartSharedOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      }
    };

    // 1. Daily Submissions Line Chart
    var dailyEl = document.getElementById('dailyChart');
    if (dailyEl && dailyData && dailyData.length) {
      new Chart(dailyEl, {
        type: 'line',
        data: {
          labels: dailyData.map(function(d) { return d.day; }),
          datasets: [{
            label: 'Submissions',
            data: dailyData.map(function(d) { return d.count; }),
            borderColor: '#0f172a',
            backgroundColor: 'rgba(15, 23, 42, 0.05)',
            fill: true,
            tension: 0.2,
            pointRadius: 2,
            pointHoverRadius: 4,
            pointBackgroundColor: '#0f172a',
            borderWidth: 2
          }]
        },
        options: Object.assign({}, chartSharedOptions, {
          scales: {
            x: {
              ticks: { maxTicksLimit: 12, font: defaultFont, color: '#64748b' },
              grid: { display: false }
            },
            y: {
              beginAtZero: true,
              ticks: { font: defaultFont, color: '#64748b', precision: 0 },
              grid: { color: '#f1f5f9' }
            }
          },
          interaction: { intersect: false, mode: 'index' }
        })
      });
    }

    // 2. Status Breakdown Doughnut Chart
    var statusEl = document.getElementById('statusChart');
    if (statusEl && statusData && statusData.length) {
      new Chart(statusEl, {
        type: 'doughnut',
        data: {
          labels: statusData.map(function(d) { return (d.status || '').replace('_', ' ').toUpperCase(); }),
          datasets: [{
            data: statusData.map(function(d) { return d.count; }),
            backgroundColor: statusData.map(function(d) { return STATUS_COLORS[d.status] || '#cbd5e1'; }),
            borderWidth: 2,
            borderColor: '#ffffff'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '70%',
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                boxWidth: 10,
                boxHeight: 10,
                padding: 12,
                font: defaultFont,
                color: '#475569'
              }
            }
          }
        }
      });
    }

    // 3. Monthly Volume Bar Chart
    var monthlyEl = document.getElementById('monthlyChart');
    if (monthlyEl && monthlyData && monthlyData.length) {
      new Chart(monthlyEl, {
        type: 'bar',
        data: {
          labels: monthlyData.map(function(d) { return d.month; }),
          datasets: [{
            label: 'Submissions',
            data: monthlyData.map(function(d) { return d.count; }),
            backgroundColor: '#334155',
            hoverBackgroundColor: '#0f172a',
            borderRadius: 4
          }]
        },
        options: Object.assign({}, chartSharedOptions, {
          scales: {
            x: {
              ticks: { maxTicksLimit: 12, font: defaultFont, color: '#64748b' },
              grid: { display: false }
            },
            y: {
              beginAtZero: true,
              ticks: { font: defaultFont, color: '#64748b', precision: 0 },
              grid: { color: '#f1f5f9' }
            }
          }
        })
      });
    }

    // 4. Volume by Form Definition Horizontal Bar
    var byFormEl = document.getElementById('byFormChart');
    if (byFormEl && byFormData && byFormData.length) {
      new Chart(byFormEl, {
        type: 'bar',
        data: {
          labels: byFormData.map(function(d) { return d.form_definition__name; }),
          datasets: [{
            label: 'Submissions',
            data: byFormData.map(function(d) { return d.count; }),
            backgroundColor: '#0f172a',
            hoverBackgroundColor: '#1e293b',
            borderRadius: 4
          }]
        },
        options: Object.assign({}, chartSharedOptions, {
          indexAxis: 'y',
          scales: {
            x: {
              beginAtZero: true,
              ticks: { font: defaultFont, color: '#64748b', precision: 0 },
              grid: { color: '#f1f5f9' }
            },
            y: {
              ticks: { font: defaultFont, color: '#334155' },
              grid: { display: false }
            }
          }
        })
      });
    }
  });
})();
