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
        tds = "<td>"+element.text+"</td><td class='status bg-"+colour+"'>"+element.status+"</td>";
        if ($('#'+element.id).length == 0) {
            $('tbody').append('<tr class="h1" id="'+element.id+'">'+tds+'</tr>');
        } else {
            $('#'+element.id).html(tds);
        }
    });
    adjustTableCompactness();
    checkAllGreen();
    function rowclick () {
        socket.emit('toggle_state', {id: $(this).attr('id')});
    };
    $('table tr').off('click').on('click', rowclick);
}

function adjustTableCompactness() {
    var $table = $('.table');
    var $container = $('.table-container');
    var $tbody = $('tbody');
    var rowCount = $tbody.find('tr').length;
    
    if (rowCount === 0) return;
    
    // Get available height (minus padding and header)
    var containerHeight = $container.height();
    var headerHeight = $('thead').outerHeight() || 50; // fallback if header not rendered yet
    var availableHeight = containerHeight - headerHeight - 40; // 40px for padding/margins
    
    // Calculate optimal height per row
    var optimalRowHeight = availableHeight / rowCount;
    
    console.log('Container height:', containerHeight);
    console.log('Header height:', headerHeight);
    console.log('Available height for rows:', availableHeight);
    console.log('Row count:', rowCount);
    console.log('Optimal row height:', optimalRowHeight);
    
    // Remove existing compactness classes
    $table.removeClass('compact very-compact ultra-compact');
    
    // Determine appropriate font size based on available row height
    // Font size should be roughly 60-70% of row height for good readability
    var targetFontSize = optimalRowHeight * 0.6;
    
    console.log('Target font size:', targetFontSize + 'px');
    
    // Apply appropriate class based on calculated font size
    if (targetFontSize >= 64) { // 4rem at 16px base
        // Use default (4rem)
        console.log('Using default size');
    } else if (targetFontSize >= 35) { // ~2.2rem
        $table.addClass('compact');
        console.log('Using compact');
    } else if (targetFontSize >= 27) { // ~1.7rem
        $table.addClass('very-compact');
        console.log('Using very-compact');
    } else {
        $table.addClass('ultra-compact');
        console.log('Using ultra-compact');
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