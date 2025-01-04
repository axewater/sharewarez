document.addEventListener('DOMContentLoaded', function() {
    // Fetch statistics data from the server
    fetch('/admin/statistics/data')
        .then(response => response.json())
        .then(data => {
            // Downloads per user chart
            new Chart(document.getElementById('downloadsPerUserChart'), {
                type: 'bar',
                data: {
                    labels: data.downloads_per_user.labels,
                    datasets: [{
                        label: 'Downloads per User',
                        data: data.downloads_per_user.data,
                        backgroundColor: 'rgba(54, 162, 235, 0.5)'
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Downloads per User'
                        }
                    }
                }
            });

            // Top downloaded games chart
            new Chart(document.getElementById('topGamesChart'), {
                type: 'bar',
                data: {
                    labels: data.top_games.labels,
                    datasets: [{
                        label: 'Most Downloaded Games',
                        data: data.top_games.data,
                        backgroundColor: 'rgba(255, 99, 132, 0.5)'
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Most Downloaded Games'
                        }
                    }
                }
            });

            // Download trends chart
            new Chart(document.getElementById('downloadTrendsChart'), {
                type: 'line',
                data: {
                    labels: data.download_trends.labels,
                    datasets: [{
                        label: 'Downloads Over Time',
                        data: data.download_trends.data,
                        borderColor: 'rgba(75, 192, 192, 1)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Download Trends'
                        }
                    }
                }
            });

            // Invite tokens per user chart
            new Chart(document.getElementById('inviteTokensChart'), {
                type: 'bar',
                data: {
                    labels: data.users_with_invites.labels,
                    datasets: [{
                        label: 'Invite Tokens Generated',
                        data: data.users_with_invites.data,
                        backgroundColor: 'rgba(75, 192, 192, 0.5)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Users with Invite Tokens Generated'
                        }
                    },
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });

            // Top downloaders chart
            new Chart(document.getElementById('topDownloadersChart'), {
                type: 'bar',
                data: {
                    labels: data.top_downloaders.labels,
                    datasets: [{
                        label: 'Users with Most Downloads',
                        data: data.top_downloaders.data,
                        backgroundColor: 'rgba(153, 102, 255, 0.5)'
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Top Downloaders'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });

            // Top collectors chart
            new Chart(document.getElementById('topCollectorsChart'), {
                type: 'bar',
                data: {
                    labels: data.top_collectors.labels,
                    datasets: [{
                        label: 'Users with Most Favorites',
                        data: data.top_collectors.data,
                        backgroundColor: 'rgba(255, 159, 64, 0.5)'
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Top Game Collectors'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        });
});
