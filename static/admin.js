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
function updateData(data) {
    data.forEach(element => {
        tds = '<td id="'+element.id+'">'+element.id+'</td><td><input class="form-control" value="'+element.text+'"/></td><td>'+element.status+'</td><td>'+element.order+'</td><td class="fit"><button id="up" class="btn btn-info btn-sm">Up</button>  <button id="down" class="btn btn-info btn-sm">Down</button>  <button id="save" class="btn btn-success btn-sm">Save</button> <button id="delete" class="btn btn-danger btn-sm">Delete</button></td>';
        if ($('#'+element.id).length == 0) {
            $('tbody').append('<tr id="'+element.id+'">'+tds+'</tr>');
        } else {
            $('#'+element.id).html(tds);
        }
    });
};
socket.on('partial_data', function (data) {
    updateData(data);
});
socket.on('all_data', function (data) {
    $('tbody').empty();
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
