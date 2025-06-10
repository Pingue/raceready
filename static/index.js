var socket = io();
socket.on("disconnect", () => {
    $('nav').addClass('bg-danger');
    $('h1').text('RACE READY IS DISCONNECTED');
});
socket.on('connect', function() {
    socket.emit('connecting', {data: 'Client Connecting'});
    socket.emit('request_all_data');
    $('nav').removeClass('bg-danger');
    $('h1').text('Race Ready');
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
    checkAllGreen();
    function rowclick () {
        socket.emit('toggle_state', {id: $(this).attr('id')});
    };
    $('table tr').off('click').on('click', rowclick);
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
socket.on('all_data', function (data) {
    $('tbody').empty();
    updateData(data);
});
$().ready(function() {
    $('#reset-all').click(function() {
        socket.emit('reset_all');
    });
    $.get('/checklists', function(data) {
        var select = $('#checklist-select');
        data.forEach(function(cl) {
            select.append($('<option>', { value: cl.id, text: cl.name }));
        });
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
});