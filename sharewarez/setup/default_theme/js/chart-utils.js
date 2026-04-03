/**
 * Creates a new Chart.js chart instance.
 * @param {string} canvasId - The ID of the canvas element.
 * @param {string} chartType - The type of chart (e.g., 'bar', 'pie', 'line').
 * @param {object} chartData - The data object for the chart.
 * @param {object} chartOptions - The options object for the chart.
 * @returns {Chart|null} The new Chart instance, or null if the canvas element is not found.
 */
function createChart(canvasId, chartType, chartData, chartOptions) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) {
        console.error(`Canvas element with ID '${canvasId}' not found.`);
        return null;
    }
    return new Chart(ctx.getContext('2d'), {
        type: chartType,
        data: chartData,
        options: chartOptions
    });
}
