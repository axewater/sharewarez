let modal;

document.addEventListener('DOMContentLoaded', function() {
    modal = new bootstrap.Modal(document.getElementById('fileTypeModal'));
});

function addFileType(category) {
    document.getElementById('modalTypeCategory').value = category;
    document.getElementById('modalTypeId').value = '';
    document.getElementById('fileTypeValue').value = '';
    document.querySelector('.modal-title').textContent = 'Add New File Type';
    modal.show();
}

function editFileType(button) {
    const row = button.closest('tr');
    const value = row.querySelector('.type-value').textContent;
    const id = row.dataset.id;
    const category = row.dataset.category;
    
    document.getElementById('modalTypeCategory').value = category;
    document.getElementById('modalTypeId').value = id;
    document.getElementById('fileTypeValue').value = value;
    document.querySelector('.modal-title').textContent = 'Edit File Type';
    modal.show();
}

function saveFileType() {
    const category = document.getElementById('modalTypeCategory').value;
    const id = document.getElementById('modalTypeId').value;
    const value = document.getElementById('fileTypeValue').value;

    if (!value) {
        alert('Please enter a file extension');
        return;
    }

    const method = id ? 'PUT' : 'POST';
    const data = id ? { id, value } : { value };

    fetch(`/api/file_types/${category}`, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRFUtils.getToken()
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
            return;
        }
        updateTableWithNewData(category, data);
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while saving');
    });
}

function deleteFileType(category, id) {
    if (!confirm('Are you sure you want to delete this file type?')) {
        return;
    }

    fetch(`/api/file_types/${category}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRFUtils.getToken()
        },
        body: JSON.stringify({ id })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
            return;
        }
        location.reload();
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while deleting');
    });
}

function updateTableWithNewData(category, data) {
    const table = document.getElementById(`${category}TypesTable`);
    const tbody = table.querySelector('tbody');
    
    // If editing existing row
    if (data.id) {
        const existingRow = tbody.querySelector(`tr[data-id="${data.id}"]`);
        if (existingRow) {
            existingRow.querySelector('.type-value').textContent = data.value;
            existingRow.classList.add('highlight');
            setTimeout(() => existingRow.classList.remove('highlight'), 2000);
            modal.hide();
            return;
        }
    }
    
    // Add new row
    const newRow = document.createElement('tr');
    newRow.dataset.id = data.id;
    newRow.dataset.category = category;
    newRow.innerHTML = `
        <td class="type-value">${data.value}</td>
        <td>
            <button class="btn btn-sm btn-warning" onclick="editFileType(this)">
                <i class="fas fa-edit"></i>
            </button>
            <button class="btn btn-sm btn-danger" onclick="deleteFileType('${category}', ${data.id})">
                <i class="fas fa-trash"></i>
            </button>
        </td>
    `;
    tbody.appendChild(newRow);
    modal.hide();
}
