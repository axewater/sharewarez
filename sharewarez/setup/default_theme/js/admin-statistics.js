document.addEventListener('DOMContentLoaded', function() {
    // Fetch statistics data from the server
    fetch('/admin/statistics/data')
        .then(response => response.json())
        .then(data => {
            // Downloads per user chart
            createChart('downloadsPerUserChart', 'bar', {
                labels: data.downloads_per_user.labels,
                datasets: [{
                    label: 'Downloads per User',
                    data: data.downloads_per_user.data,
                    backgroundColor: 'rgba(54, 162, 235, 0.5)'
                }]
            }, {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Downloads per User'
                    }
                }
            });

            // Top downloaded games chart
            createChart('topGamesChart', 'bar', {
                labels: data.top_games.labels,
                datasets: [{
                    label: 'Most Downloaded Games',
                    data: data.top_games.data,
                    backgroundColor: 'rgba(255, 99, 132, 0.5)'
                }]
            }, {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Most Downloaded Games'
                    }
                }
            });

            // Download trends chart
            createChart('downloadTrendsChart', 'line', {
                labels: data.download_trends.labels,
                datasets: [{
                    label: 'Downloads Over Time',
                    data: data.download_trends.data,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    tension: 0.1
                }]
            }, {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Download Trends'
                    }
                }
            });

            // Invite tokens per user chart
            createChart('inviteTokensChart', 'bar', {
                labels: data.users_with_invites.labels,
                datasets: [{
                    label: 'Invite Tokens Generated',
                    data: data.users_with_invites.data,
                    backgroundColor: 'rgba(75, 192, 192, 0.5)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                }]
            }, {
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
            });

            // Top downloaders chart
            createChart('topDownloadersChart', 'bar', {
                labels: data.top_downloaders.labels,
                datasets: [{
                    label: 'Users with Most Downloads',
                    data: data.top_downloaders.data,
                    backgroundColor: 'rgba(153, 102, 255, 0.5)'
                }]
            }, {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Top Downloaders'
                    }
                },
                scales: {
                    y: { beginAtZero: true }
                }
            });

            // Top collectors chart
            createChart('topCollectorsChart', 'bar', {
                labels: data.top_collectors.labels,
                datasets: [{
                    label: 'Users with Most Favorites',
                    data: data.top_collectors.data,
                    backgroundColor: 'rgba(255, 159, 64, 0.5)'
                }]
            }, {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Top Game Collectors'
                    }
                },
                scales: {
                    y: { beginAtZero: true }
                }
            });
        });
});
