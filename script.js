// public/script.js (Updated for Minimal Minor Visualization)

async function processGraph() {
    const fileInput = document.getElementById('json-file-input');
    const messageElement = document.getElementById('message');

    // Image 1: Original Graph
    const imageOriginalElement = document.getElementById('output-img-original');

    // Image 2: Kuratowski Subdivision
    const imageSubdivisionElement = document.getElementById('output-img-kuratowski'); // Using old ID for Subdivision
    const subdivisionLabel = document.getElementById('kuratowski-label');

    // Image 3: Minimal Kuratowski Minor (NEW Elements)
    const imageMinorElement = document.getElementById('output-img-minor');
    const minorLabel = document.getElementById('minor-label');

    // Clear previous results
    messageElement.textContent = 'Processing...';
    messageElement.style.color = 'black';

    imageOriginalElement.style.display = 'none';
    imageSubdivisionElement.style.display = 'none';
    subdivisionLabel.style.display = 'none';

    imageMinorElement.style.display = 'none'; // Clear minor image
    minorLabel.style.display = 'none';       // Clear minor label

    if (fileInput.files.length === 0) {
        messageElement.textContent = 'Please select a JSON file first.';
        messageElement.style.color = 'red';
        return;
    }

    const file = fileInput.files[0];
    const reader = new FileReader();

    reader.onload = async function(event) {
        try {
            const graphData = JSON.parse(event.target.result);

            const API_URL = '/api/planarity';

            const response = await fetch(API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(graphData)
            });

            const data = await response.json();

            if (response.ok && data.status === "success") {
                messageElement.textContent = `Result: ${data.title}`;
                messageElement.style.color = data.is_planar ? 'green' : 'red';

                // Display Original Graph (Image 1)
                imageOriginalElement.src = `data:image/png;base64,${data.image_original}`;
                imageOriginalElement.style.display = 'block';

                // Handle Non-Planar Case (Images 2 and 3)
                if (!data.is_planar && data.image_subdivision) { // Check for the subdivision image

                    // Display Kuratowski Subdivision (Image 2)
                    subdivisionLabel.textContent = `Intermediate Subdivision: ${data.kuratowski_type}`;
                    subdivisionLabel.style.display = 'block';
                    imageSubdivisionElement.src = `data:image/png;base64,${data.image_subdivision}`;
                    imageSubdivisionElement.style.display = 'block';

                    // Display Minimal Minor (Image 3)
                    minorLabel.textContent = `Minimal Kuratowski Minor (${data.kuratowski_type.replace(' Subdivision', '')})`;
                    minorLabel.style.display = 'block';
                    imageMinorElement.src = `data:image/png;base64,${data.image_minor}`;
                    imageMinorElement.style.display = 'block';

                } else {
                    // Hide Kuratowski elements if planar
                    imageSubdivisionElement.style.display = 'none';
                    subdivisionLabel.style.display = 'none';
                    imageMinorElement.style.display = 'none';
                    minorLabel.style.display = 'none';
                }

            } else {
                // Handle API errors
                messageElement.textContent = `Error: ${data.error || 'Unknown server error'}`;
                messageElement.style.color = 'red';
                console.error("API Error:", data);
            }

        } catch (error) {
            messageElement.textContent = `File Error: Invalid JSON or network issue. (${error.message})`;
            messageElement.style.color = 'red';
            console.error("File Read Error:", error);
        }
    };

    reader.onerror = function() {
        messageElement.textContent = 'Failed to read file.';
        messageElement.style.color = 'red';
    };

    reader.readAsText(file);
}