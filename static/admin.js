function updateData(data) {
    console.log("Updating data");
    tbody = $('tbody#actions');
    console.log(tbody);
    console.log(tbody.length);

    data.forEach(element => {
        var notes = element.notes || '';
        tds = '<td id="'+element.id+'">'+element.id+'</td><td><input class="form-control action-input" value="'+element.text+'"/></td><td><input class="form-control notes-input" value="'+notes+'"/></td><td>'+element.status+'</td><td>'+element.order+'</td><td class="fit"><button id="up" class="btn btn-info btn-sm">Up</button>  <button id="down" class="btn btn-info btn-sm">Down</button>  <button id="save" class="btn btn-success btn-sm">Save</button> <button id="delete" class="btn btn-danger btn-sm">Delete</button></td>';
        if ($('#'+element.id).length == 0) {
            $('tbody#actions').append('<tr id="'+element.id+'">'+tds+'</tr>');
        } else {
            $('#'+element.id).html(tds);
        }
    });
    console.log(tbody.length);

};

var socket = io(); // Move socket to global scope


function loadChecklistsTable() {
    socket.once('checklists', function(data) {
        console.log("Updating checklists")
        var tbody = $('tbody#checklists');
        console.log(tbody);
        console.log(tbody.length);
        tbody.empty();
        data.forEach(function(cl) {
            var row = $('<tr>');
            row.append('<td>' + cl.id + '</td>');
            row.append('<td>' + (cl.order_pos || 0) + '</td>');
            row.append('<td><input type="text" class="form-control checklist-name" value="' + cl.name + '" data-id="' + cl.id + '"/></td>');
            row.append(
                '<td>' +
                '<button class="btn btn-info btn-sm move-checklist-up" data-id="' + cl.id + '">Up</button> ' +
                '<button class="btn btn-info btn-sm move-checklist-down" data-id="' + cl.id + '">Down</button> ' +
                '<button class="btn btn-warning btn-sm rename-checklist" data-id="' + cl.id + '">Rename</button> ' +
                '<button class="btn btn-danger btn-sm delete-checklist" data-id="' + cl.id + '">Delete</button>' +
                '</td>'
            );
            tbody.append(row);
        });
        console.log(tbody.length);
    });
    
    socket.emit('get_checklists');
}

$(document).ready(function() {
    socket.on("disconnect", () => {
        $('nav').addClass('bg-danger');
        $('h1').text('RACE READY IS DISCONNECTED');
    });
    socket.on('connect', function() {
        socket.emit('connecting', {data: 'Client Connecting'});
        socket.emit('request_all_data');
        $('nav').removeClass('bg-danger');
        $('h1').text('Race Ready Admin');
    });
    socket.on('error', function (message) {
        console.error('Socket error:', message);
    });
    socket.on('partial_data', function (data) {
        updateData(data);
    });
    socket.on('current_phase', function (data) {
        if (data.current_phase) {
            $('h1').text('Race Ready Admin - ' + data.current_phase);
        }
    });
    socket.on('checklist_moved', function (data) {
        if (data.success) {
            loadChecklistsTable();
            updateChecklistDropdown();
        }
    });
    socket.on('all_data', function (data) {
        $('tbody#actions').empty();
        var actions = data.actions || data; // Handle both new format and legacy format
        updateData(actions);
        
        // Update title with current phase if provided
        if (data.current_phase) {
            $('h1').text('Race Ready Admin - ' + data.current_phase);
        }
        
        // Extract current checklist ID from the data and update dropdown
        if (actions.length > 0) {
            var currentChecklistId = actions[0].checklist_id;
            var select = $('#checklist-select');
            if (select.find('option').length > 0) {
                select.val(currentChecklistId);
                select.find('option').prop('selected', false);
                select.find('option[value="' + currentChecklistId + '"]').prop('selected', true);
            }
        }
    });
    socket.on('deleted', function (data) {
        $('#'+data.id).remove();
    });
    $(document).on('click', '#up', function() {
        var id = $(this).closest('tr').attr('id');
        socket.emit('up', {id: id});
    });
    $(document).on('click', '#down', function() {
        var id = $(this).closest('tr').attr('id');
        socket.emit('down', {id: id});
    });
    $(document).on('click', '#save', function() {
        var id = $(this).closest('tr').attr('id');
        var text = $(this).closest('tr').find('.action-input').val();
        var notes = $(this).closest('tr').find('.notes-input').val();
        socket.emit('save', {id: id, text: text, notes: notes});
    });
    $(document).on('click', '#delete', function() {
        var id = $(this).closest('tr').attr('id');
        socket.emit('delete', {id: id});
    });
    $(document).on('click', '#add', function() {
        socket.emit('add', {text: 'New Item'});
    });

    $('#checklist-select').on('change', function() {
        var checklist_id = $(this).val();
        socket.emit('set_checklist', { checklist_id: checklist_id });
    });

    loadChecklistsTable();
    updateChecklistDropdown();

    // Add checklist
    $('#add-checklist-btn').on('click', function() {
        var name = prompt("Enter new checklist name:");
        if (name) {
            $.post({
                url: '/create_checklist',
                data: JSON.stringify({ name }),
                contentType: 'application/json',
                success: function() {
                    loadChecklistsTable();
                    updateChecklistDropdown();
                }
            });
        }
    });

    // Rename checklist
    $('#checklists-table').on('click', '.rename-checklist', function() {
        var id = $(this).data('id');
        var name = $(this).closest('tr').find('.checklist-name').val();
        if (name) {
            $.post({
                url: '/rename_checklist',
                data: JSON.stringify({ id, name }),
                contentType: 'application/json',
                success: function() {
                    loadChecklistsTable();
                    updateChecklistDropdown();
                }
            });
        }
    });

    // Delete checklist
    $('#checklists-table').on('click', '.delete-checklist', function() {
        var id = $(this).data('id');
        if (confirm("Are you sure you want to delete this checklist?")) {
            $.ajax({
                url: '/delete_checklist',
                type: 'POST',
                data: JSON.stringify({ id }),
                contentType: 'application/json',
                success: function() {
                    loadChecklistsTable();
                    updateChecklistDropdown();
                }
            });
        }
    });

    // Move checklist up
    $('#checklists-table').on('click', '.move-checklist-up', function() {
        var id = $(this).data('id');
        socket.emit('move_checklist_up', { id: id });
    });

    // Move checklist down
    $('#checklists-table').on('click', '.move-checklist-down', function() {
        var id = $(this).data('id');
        socket.emit('move_checklist_down', { id: id });
    });
});
function updateChecklistDropdown() {
    // Simple approach - just get the data and update
    socket.once('checklists', function(checklists) {
        socket.once('current_checklist', function(currentData) {
            console.log('Checklists loaded:', checklists);
            console.log('Current checklist:', currentData);
            var select = $('#checklist-select');
            if (select.length === 0) return; // Only update if dropdown exists
            select.empty();
            checklists.forEach(function(cl) {
                var option = $('<option>', { value: cl.id, text: cl.name });
                if (cl.id == currentData.current_checklist_id) {
                    option.attr('selected', 'selected');
                }
                select.append(option);
            });
        });
        socket.emit('get_current_checklist');
    });
    
    socket.emit('get_checklists');
}




// Remaining to do:
// - Button for next checklist
// - Test companion export with normalised stuff. It probably needs an update to emit the new event