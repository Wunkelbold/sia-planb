//import { Dropdown} from "mdb-ui-kit";

//initMDB({ Dropdown });

const sections = document.querySelectorAll('.section');
let options = {
    root: null,
    threshold: 0.5  // Trigger action when at least 50% of section is visible
};

let observer = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            // Smoothly scroll to the section
            entry.target.scrollIntoView({
                behavior: 'smooth'
            });
        }
    });
}, options);

sections.forEach(section => {
    observer.observe(section);
});

document.addEventListener("DOMContentLoaded", function () {
    if (typeof jQuery === "undefined") {
        console.error("Error: jQuery is not loaded before Bootstrap!");
    } else {
        console.log("jQuery is loaded, Bootstrap will work.");
    }
});

