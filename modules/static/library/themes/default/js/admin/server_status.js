// Initialize data from template
let cpuUsage, memoryUsage, diskUsage;

// Function to initialize data passed from template
function initializeServerData(data) {
    cpuUsage = data.cpuUsage;
    memoryUsage = data.memoryUsage;
    diskUsage = data.diskUsage;
}

// Update CPU progress bar color based on usage
function updateCpuBar() {
    const cpuBar = document.getElementById('cpuBar');
    if (!cpuBar || !cpuUsage) return;
    
    if (cpuUsage > 90) {
        cpuBar.classList.add('bg-danger');
    } else if (cpuUsage > 50) {
        cpuBar.classList.add('bg-warning');
    } else {
        cpuBar.classList.add('bg-success');
    }
}

// Initialize Memory Usage Chart
function initializeMemoryChart() {
    if (!memoryUsage) return;
    
    const memoryContext = document.getElementById('memoryChart').getContext('2d');
    new Chart(memoryContext, {
        type: 'pie',
        data: {
            labels: ['Used', 'Available'],
            datasets: [{
                data: [memoryUsage.used, memoryUsage.available],
                backgroundColor: [
                    'rgba(255, 99, 132, 0.8)',
                    'rgba(75, 192, 192, 0.8)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ': ' + 
                                   (context.label === 'Used' ? memoryUsage.used_formatted : memoryUsage.available_formatted);
                        }
                    }
                }
            }
        }
    });
}

// Initialize Disk Usage Chart
function initializeDiskChart() {
    if (!diskUsage) return;
    
    const diskContext = document.getElementById('diskChart').getContext('2d');
    new Chart(diskContext, {
        type: 'pie',
        data: {
            labels: ['Used', 'Free'],
            datasets: [{
                data: [diskUsage.used, diskUsage.free],
                backgroundColor: [
                    'rgba(255, 99, 132, 0.8)',
                    'rgba(75, 192, 192, 0.8)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ': ' + 
                                   (context.label === 'Used' ? diskUsage.used_formatted : diskUsage.free_formatted);
                        }
                    }
                }
            }
        }
    });
}

// Initialize all charts and components
function initializeServerStatus() {
    updateCpuBar();
    initializeMemoryChart();
    initializeDiskChart();
}
