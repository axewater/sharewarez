let highestZIndex = 0;


// Setting initial positions if necessary
$(document).ready(function() {
    let list1InitialTop = '80px';
    let list1InitialLeft = '10px';

    let list2InitialTop = '80px';
    let list2InitialLeft = '280px';
	
	let list3InitialTop = '80px';
    let list3InitialLeft = '490px';
	
	let list4InitialTop = '80px';
    let list4InitialLeft = '700px';
	
    $("#list-1").css({top: list1InitialTop, left: list1InitialLeft});
    $("#list-2").css({top: list2InitialTop, left: list2InitialLeft});
	$("#list-3").css({top: list1InitialTop, left: list3InitialLeft});
    $("#list-4").css({top: list2InitialTop, left: list4InitialLeft});
});



$(function() {
    $(".list").draggable({
        revert: false,  // This ensures that the list doesn't revert to its original position
        start: function(event, ui) {
            // Sound
            $("#pickup-sound")[0].play();

            // Bring the currently dragged item to the front
            $(this).css("z-index", 1000);
			    highestZIndex += 1;
			$(this).css("z-index", highestZIndex);

            // Diagonal morph
            $(this).css({
                transform: "rotate(-2deg) skewX(8deg) scale(1.05)"
            });
        },
        stop: function(event, ui) {
            // Sound
            $("#drop-sound")[0].play();



            // Bounce animation and reset morph
            $(this).css({
                animation: "bounce 0.2s",
                transform: "rotate(0deg) skewX(0) scale(1)"
            });

            setTimeout(() => {
                $(this).css("animation", "");  // Clear the animation after it plays
            }, 400);
        }
    });
	
	
	
	
	
	
	
	
	
});
