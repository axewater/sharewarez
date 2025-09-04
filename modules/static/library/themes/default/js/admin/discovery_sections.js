document.addEventListener('DOMContentLoaded', function() {
    const sectionsList = document.getElementById('discovery-sections-list');
    
    // Initialize Sortable.js
    new Sortable(sectionsList, {
        animation: 150,
        handle: '.drag-handle',
        ghostClass: 'sortable-ghost',
        dragClass: 'sortable-drag',
        onEnd: function(evt) {
            updateSectionOrder();
        }
    });

    // Handle visibility toggles
    document.querySelectorAll('.section-visibility-toggle').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const sectionId = this.dataset.sectionId;
            updateSectionVisibility(sectionId, this.checked);
        });
    });

    // Update section order in database
    function updateSectionOrder() {
        const sections = document.querySelectorAll('.section-item');
        const orderData = Array.from(sections).map((section, index) => ({
            id: section.dataset.sectionId,
            order: index
        }));

        fetch('/admin/api/discovery_sections/order', {
            method: 'POST',
            headers: CSRFUtils.getHeaders({
                'Content-Type': 'application/json'
            }),
            body: JSON.stringify({ sections: orderData })
        })
        .then(response => response.json())
        .then(handleResponse)
        .catch(error => {
            console.error('Error:', error);
            $.notify("Error updating section order", "error");
        });
    }

    function handleResponse(data) {
        if (data.success) {
            $.notify("Section order updated successfully", "success");
        } else {
            $.notify("Failed to update section order: " + (data.error || "Unknown error"), "error");
        }
    }

    // Update section visibility in database
    function updateSectionVisibility(sectionId, isVisible) {
        fetch('/admin/api/discovery_sections/visibility', {
            method: 'POST',
            headers: CSRFUtils.getHeaders({
                'Content-Type': 'application/json'
            }),
            body: JSON.stringify({
                section_id: sectionId,
                is_visible: isVisible
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                $.notify("Section visibility updated successfully", "success");
            } else {
                $.notify("Failed to update section visibility", "error");
            }
        })
        .catch(error => {
            console.error('Error:', error);
            $.notify("Error updating section visibility", "error");
        });
    }
});
