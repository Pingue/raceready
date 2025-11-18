var socket = io();
socket.on("disconnect", () => {
    $('nav').addClass('bg-danger');
    $('h1').text('RACE READY IS DISCONNECTED');
});
socket.on('connect', function() {
    socket.emit('connecting', {data: 'Client Connecting'});
    socket.emit('request_all_data');
    $('nav').removeClass('bg-danger');
    $('h1').text('Race Ready'); // This will be updated when data loads
});
socket.on('deleted', function (data) {
    $('#'+data.id).remove();
    checkAllGreen();
});
function updateData(data) {
    data.forEach(element => {
        if (element.status == 1) {
            var colour = 'success';
        } else {
            var colour = 'danger';
        }
        if (element.status == 1) {
            element.status = 'Ready';
        } else {
            element.status = 'Not Ready';
        }
        
        // Create edit button
        // var editBtn = '<button class="btn btn-primary btn-sm edit-btn" data-id="' + element.id + '">Edit</button>';
        // var saveBtn = '<button class="btn btn-success btn-sm save-btn" data-id="' + element.id + '" style="display:none;">Save</button>';
        // var cancelBtn = '<button class="btn btn-secondary btn-sm cancel-btn" data-id="' + element.id + '" style="display:none;">Cancel</button>';
        
        var notes = element.notes || '';
        
        tds = "<td class='action-text'>" + element.text + "</td><td class='notes-text'>" + notes + "</td><td class='status bg-" + colour + "'>" + element.status + "</td>";// <td class='edit-cell'>" + editBtn + saveBtn + cancelBtn + "</td>";
        
        if ($('#'+element.id).length == 0) {
            $('tbody').append('<tr class="h1" id="'+element.id+'">'+tds+'</tr>');
        } else {
            $('#'+element.id).html(tds);
        }
    });
    adjustTableCompactness();
    checkAllGreen();
    
    // Row click for toggle (but not on edit buttons)
    function rowclick(e) {
        if (!$(e.target).hasClass('btn') && !$(e.target).hasClass('form-control')) {
            socket.emit('toggle_state', {id: $(this).attr('id')});
        }
    }
    $('table tr').off('click').on('click', rowclick);
    
    /*
    // Edit button functionality
    $('.edit-btn').off('click').on('click', function(e) {
        e.stopPropagation();
        var rowId = $(this).data('id');
        var row = $('#' + rowId);
        var actionCell = row.find('.action-text');
        var notesCell = row.find('.notes-text');
        var currentText = actionCell.text();
        var currentNotes = notesCell.text();
        
        // Replace text with input fields
        actionCell.html('<input type="text" class="form-control action-input" value="' + currentText + '" data-original="' + currentText + '">');
        notesCell.html('<input type="text" class="form-control notes-input" value="' + currentNotes + '" data-original="' + currentNotes + '">');
        
        // Show save/cancel, hide edit
        $(this).hide();
        row.find('.save-btn, .cancel-btn').show();
    });
    
    // Save button functionality
    $('.save-btn').off('click').on('click', function(e) {
        e.stopPropagation();
        var rowId = $(this).data('id');
        var row = $('#' + rowId);
        var actionInput = row.find('.action-input');
        var notesInput = row.find('.notes-input');
        var newText = actionInput.val();
        var newNotes = notesInput.val();
        
        // Send update to server using existing 'save' event
        socket.emit('save', {id: rowId, text: newText, notes: newNotes});
        
        // Reset UI
        resetEditUI(row, newText, newNotes);
    });
    
    // Cancel button functionality
    $('.cancel-btn').off('click').on('click', function(e) {
        e.stopPropagation();
        var rowId = $(this).data('id');
        var row = $('#' + rowId);
        var actionInput = row.find('.action-input');
        var notesInput = row.find('.notes-input');
        var originalText = actionInput.data('original');
        var originalNotes = notesInput.data('original');
        
        // Reset UI without saving
        resetEditUI(row, originalText, originalNotes);
    });
    */
}

function resetEditUI(row, text, notes) {
    var actionCell = row.find('.action-text');
    var notesCell = row.find('.notes-text');
    actionCell.html(text);
    notesCell.html(notes);
    row.find('.edit-btn').show();
    row.find('.save-btn, .cancel-btn').hide();
}

function adjustTableCompactness() {
    var $table = $('.table');
    var $container = $('.table-container');
    var $tbody = $('tbody');
    var $rows = $tbody.find('tr');
    var rowCount = $rows.length;
    
    if (rowCount === 0) return;
    
    // Get available height (minus padding and header)
    var containerHeight = $container.height();
    var headerHeight = $('thead').outerHeight() || 50;
    var availableHeight = containerHeight - headerHeight - 40; // 40px for padding/margins
    
    console.log('Container height:', containerHeight);
    console.log('Header height:', headerHeight);
    console.log('Available height for rows:', availableHeight);
    console.log('Row count:', rowCount);
    
    // Remove any class-based sizing and use direct font-size control
    $table.removeClass('compact very-compact ultra-compact');
    
    // Start with a large font size and decrease until it fits
    var startFontSize = 64; // Start at 64px (4rem)
    var minFontSize = 16;   // Don't go below 16px (1rem)
    var decrement = 1;      // Decrease by 5px each iteration
    var currentFontSize = startFontSize;
    
    while (currentFontSize >= minFontSize) {
        // Apply font size directly to rows
        $rows.css('font-size', currentFontSize + 'px');
        
        // Scale padding proportionally to font size
        // At 64px font, use 12px padding (0.75rem)
        // Scale linearly: padding = (font-size / 64) * 12
        var scaledPadding = (currentFontSize / 64) * 12;
        $rows.find('td').css('padding', scaledPadding + 'px');
        
        // Force a reflow to get accurate measurements
        $tbody[0].offsetHeight;
        
        // Measure actual tbody height
        var tbodyHeight = $tbody.outerHeight();
        
        console.log('Trying font-size:', currentFontSize + 'px, padding:', scaledPadding.toFixed(2) + 'px, tbody height:', tbodyHeight);
        
        // Check if it fits
        if (tbodyHeight <= availableHeight) {
            console.log('Content fits with font-size:', currentFontSize + 'px, padding:', scaledPadding.toFixed(2) + 'px');
            break;
        }
        
        // Try next smaller size
        currentFontSize -= decrement;
    }
    
    // If even the smallest size doesn't fit, we'll keep the minimum
    if (currentFontSize < minFontSize) {
        console.log('Using minimum font-size:', minFontSize + 'px - content may still overflow');
        $rows.css('font-size', minFontSize + 'px');
        var minPadding = (minFontSize / 64) * 12;
        $rows.find('td').css('padding', minPadding + 'px');
    }
}
function checkAllGreen() {
    var allgreen = true;
    $('table tr .status').each(function() {
        if ($(this).text() != 'Ready') {
            allgreen = false;
        }
    });
    if (allgreen) {
        $('body').css('background-color', 'lightgreen');
    } else {
        $('body').css('background-color', '');
    }
};
socket.on('partial_data', function (data) {
    updateData(data);
});
socket.on('current_phase', function (data) {
    if (data.current_phase) {
        $('h1').text('Race Ready - ' + data.current_phase);
    }
});
socket.on('all_data', function (data) {
    $('tbody').empty();
    var actions = data.actions || data; // Handle both new format and legacy format
    updateData(actions);
    
    // Update title with current phase if provided
    if (data.current_phase) {
        $('h1').text('Race Ready - ' + data.current_phase);
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
socket.on('error', function (message) {
    console.error('Socket error:', message);
});
$().ready(function() {
    $('#reset-all').click(function() {
        socket.emit('reset_all');
    });
    
    // Adjust table compactness on window resize
    $(window).on('resize', function() {
        adjustTableCompactness();
    });
    
    // Load checklists and set the current one as selected using WebSocket
    socket.once('checklists', function(checklists) {
        socket.once('current_checklist', function(currentData) {
            console.log('Checklists loaded:', checklists);
            console.log('Current checklist:', currentData);
            var select = $('#checklist-select');
            select.empty(); // Clear any existing options
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
    
    // Request the data
    socket.emit('get_checklists');

    $('#checklist-select').on('change', function() {
        var checklist_id = $(this).val();
        socket.emit('set_checklist', { checklist_id: checklist_id });
    });
});