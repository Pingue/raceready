
function updateData(data) {
    console.log("Updating data");
    tbody = $('tbody#actions');
    console.log(tbody);
    console.log(tbody.length);

    data.forEach(element => {
        tds = '<td id="'+element.id+'">'+element.id+'</td><td><input class="form-control" value="'+element.text+'"/></td><td>'+element.status+'</td><td>'+element.order+'</td><td class="fit"><button id="up" class="btn btn-info btn-sm">Up</button>  <button id="down" class="btn btn-info btn-sm">Down</button>  <button id="save" class="btn btn-success btn-sm">Save</button> <button id="delete" class="btn btn-danger btn-sm">Delete</button></td>';
        if ($('#'+element.id).length == 0) {
            $('tbody#actions').append('<tr id="'+element.id+'">'+tds+'</tr>');
        } else {
            $('#'+element.id).html(tds);
        }
    });
    console.log(tbody.length);

};


function loadChecklistsTable() {
    $.get('/checklists', function(data) {
        console.log("Updating checklists")
        var tbody = $('tbody#checklists');
        console.log(tbody);
        console.log(tbody.length);
        tbody.empty();
        data.forEach(function(cl) {
            var row = $('<tr>');
            row.append('<td>' + cl.id + '</td>');
            row.append('<td><input type="text" class="form-control checklist-name" value="' + cl.name + '" data-id="' + cl.id + '"/></td>');
            row.append(
                '<td>' +
                '<button class="btn btn-warning btn-sm rename-checklist" data-id="' + cl.id + '">Rename</button> ' +
                '<button class="btn btn-danger btn-sm delete-checklist" data-id="' + cl.id + '">Delete</button>' +
                '</td>'
            );
            tbody.append(row);
        });
        console.log(tbody.length);

    });
}

$(document).ready(function() {
    var socket = io();
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
    socket.on('partial_data', function (data) {
        updateData(data);
    });
    socket.on('all_data', function (data) {
        $('tbody#actions').empty();
        updateData(data);
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
        var text = $(this).closest('tr').find('input').val();
        socket.emit('save', {id: id, text: text});
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
        $.ajax({
            url: '/set_checklist',
            type: 'POST',
            data: JSON.stringify({ checklist_id }),
            contentType: 'application/json',
            success: function() {
                socket.emit('request_all_data');
            }
        });
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
});
function updateChecklistDropdown() {
    $.get('/checklists', function(data) {
        var select = $('#checklist-select');
        if (select.length === 0) return; // Only update if dropdown exists
        select.empty();
        data.forEach(function(cl) {
            select.append($('<option>', { value: cl.id, text: cl.name }));
        });
    });
}




// Remaining to do:
// - Button for next checklist
// - Test companion export with normalised stuff. It probably needs an update to emit the new event