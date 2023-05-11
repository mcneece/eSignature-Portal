//This function listens to the Toggle on the find admin tool and displays the appropriate search bar and label
function toggleSlider() {
    // Get the checkbox
    var checkBox = document.getElementById("slider");
    // Get the search boxes
    var searchemail = document.getElementById("mySearch");
    var searchgroup = document.getElementById("mySearch2");

    var grouplabel = document.getElementById("group_label");
    var emaillabel = document.getElementById("email_label");
    var emailtext = document.getElementById("emailHelp")
    var grouptext = document.getElementById("GroupHelp")
  
    // If the checkbox is checked, display the output text
    if (checkBox.checked == false){
      searchgroup.style.display = "none";
      searchemail.style.display = "inline-block";
      grouplabel.style.display = "none";
      emaillabel.style.display = "inline-block";
      grouptext.style.display = "none";
      emailtext.style.display = "inline-block";
    } else {
      searchgroup.style.display = "inline-block";
      searchemail.style.display = "none";
      grouplabel.style.display = "inline-block";
      emaillabel.style.display = "none";
      grouptext.style.display = "inline-block";
      emailtext.style.display = "none";
    }
  }