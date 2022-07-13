//This function listens to the Toggle on the admin page and displays the appropriate search bar
function toggleSlider() {
    // Get the checkbox
    var checkBox = document.getElementById("slider");
    // Get the search boxes
    var searchemail = document.getElementById("mySearch");
    var searchgroup = document.getElementById("mySearch2");
  
    // If the checkbox is checked, display the output text
    if (checkBox.checked == false){
      searchemail.style.display = "none";
      searchgroup.style.display = "inline-block";
    } else {
      searchemail.style.display = "inline-block";
      searchgroup.style.display = "none";
    }
  }