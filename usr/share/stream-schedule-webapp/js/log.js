function setDatePicker(){
	$(".datepicker").datepicker();
	$(".datepicker").datepicker( "option", "dateFormat", 'yy-mm-dd' );
	$(".datepicker").datepicker( "option", "firstDay", '1' );

	var date = new RegExp('[\\?&]' + 'date' + '=([^&#]*)').exec(window.location.href) || 0;
	if (date == 0){
		$(".datepicker").datepicker( "setDate" , 'today' );
		$('#form').submit();
	}else{
		$(".datepicker").datepicker( "setDate" , date[1] );
		$('.datepicker').change(
			function() {
				$('#form').submit();
			}
		);
	}
}

function markUp(){
	var okays=new Array(
		'Source logging in at mountpoint',
		'Connection setup was successful',
		'accepted',
		'server started',
		'LOG START',
		'Switch to src_',
		'Method "OGG" ',
		'Method "MP3" ',
		'Decoding...'
	);
	var infos=new Array(
//			'Switch to http_input_fallback',
		'Connecting mount',
		'RELOAD	schedule',
		'INIT',
		'PLAY',
		'liquidsoap station'
	);
	var errors=new Array(
		'Shutdown started',
		'Shutting down',
		'Source failed',
		'Underrun',
		'ERROR',
		'Alsa error: Device or resource busy!',
		'source_shutdown',
		'LOG END',
		'Switch to net_outage',
		'[net_outage',
		'Feeding stopped: source stopped',
		'Feeding stopped: Utils.Timeout',
		'Feeding stopped: Ogg.End_of_stream'
	);

	$('pre').each(
		function () {

			var str = $(this).html();
			for (word in errors){
				str = str.split(errors[word]).join('<span class="error">'+errors[word]+'</span>');
			}
			for (word in infos){
				str = str.split(infos[word]).join('<span class="info">'+infos[word]+'</span>');
			}
			for (word in okays){
				str = str.split(okays[word]).join('<span class="okay">'+okays[word]+'</span>');
			}

			$(this).html(str);
		}
	);

}

$(document).ready(
	function() {
		setDatePicker();
		markUp();
	}
);

