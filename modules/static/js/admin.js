// modules/static/js/admin.js
document.addEventListener("DOMContentLoaded", () => {
  // Get references to the relevant HTML elements
  const usersTable = document.getElementById("users-table");
  const chatbotsTable = document.getElementById("chatbots-table");

  // Attach event listeners for users table
  if (usersTable) {
    usersTable.addEventListener("click", handleUsersTableClick);
    usersTable.addEventListener("submit", handleUsersTableSubmit);
  }

  // Attach event listeners for chatbots table
  if (chatbotsTable) {
    chatbotsTable.addEventListener("click", handleChatbotsTableClick);
    chatbotsTable.addEventListener("submit", handleChatbotsTableSubmit);
  }

  // Function to handle click events in users table
  function handleUsersTableClick(event) {
    if (event.target.classList.contains("edit-btn")) {
      handleEditRow(event.target);
    } else if (event.target.classList.contains("delete-btn")) {
      handleDeleteRow(event.target);
    }
  }

  // Function to handle click events in chatbots table
  function handleChatbotsTableClick(event) {
    if (event.target.classList.contains("edit-btn")) {
      handleEditRow(event.target);
    } else if (event.target.classList.contains("delete-btn")) {
      handleDeleteRow(event.target);
    }
  }

  // Function to handle edit row action
  function handleEditRow(button) {
    const row = button.closest("tr");

    // Enable editing mode for the row
    row.classList.add("editing");
    row.querySelectorAll("input, select").forEach((input) => {
      input.disabled = false;
    });
  }

  // Function to handle delete row action
  function handleDeleteRow(button) {
    const row = button.closest("tr");

    // Confirm deletion
    if (confirm("Are you sure you want to delete this row?")) {
      // Perform deletion logic here

      // Remove the row from the table
      row.remove();
    }
  }

  // Function to handle form submissions in users table
  function handleUsersTableSubmit(event) {
    event.preventDefault();
    const form = event.target;

    // Perform form submission logic here

    // Disable editing mode for the row
    const row = form.closest("tr");
    row.classList.remove("editing");
    row.querySelectorAll("input, select").forEach((input) => {
      input.disabled = true;
    });
  }

  // Function to handle form submissions in chatbots table
  function handleChatbotsTableSubmit(event) {
    event.preventDefault();
    const form = event.target;

    // Perform form submission logic here

    // Disable editing mode for the row
    const row = form.closest("tr");
    row.classList.remove("editing");
    row.querySelectorAll("input, select").forEach((input) => {
      input.disabled = true;
    });
  }
});
