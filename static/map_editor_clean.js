// Initial setup
const mapDataElement = document.getElementById("map-data");

const mapId = mapDataElement.getAttribute("data-map-id");
let nodes = JSON.parse(mapDataElement.getAttribute("data-nodes"));
let links = JSON.parse(mapDataElement.getAttribute("data-links"));

let editorsData;
try {
    editorsData = JSON.parse(mapDataElement.getAttribute("data-editors") || "[]");
} catch (e) {
    editorsData = [];
    const listItems = document.querySelectorAll("#editors-list li");
    listItems.forEach(item => {
        if (item.textContent !== "No editors yet") {
            editorsData.push(item.textContent);
        }
    });
}

const labelToNode = {};
nodes.forEach(n => labelToNode[n.label] = n);
links = links.map(l => ({ 
    source: labelToNode[l.sourceLabel], 
    target: labelToNode[l.targetLabel], 
    type: l.type || 'line',
    distance: l.distance || 100
}));

let isLinkMode = false;
let selectedSourceNode = null;
let isDeleteMode = false;
let actionHistory = [];
let selectedResizableNode = null;
let selectedResizableLink = null;



const editorsList = document.getElementById("editors-list");
if (editorsData && editorsData.length > 0) {
    editorsData.forEach(editor => {
        const li = document.createElement("li");
        li.textContent = editor;
        editorsList.appendChild(li);
    });
} else {
    const li = document.createElement("li");
    li.textContent = "No editors yet";
    editorsList.appendChild(li);
}

// Ensure resize popup is properly styled
const resizePopup = document.getElementById("resize-popup");

// Create link resize popup
const linkResizePopup = document.createElement("div");
linkResizePopup.id = "link-resize-popup";

// Create buttons for link resizing
const increaseLinkButton = document.createElement("button");
increaseLinkButton.textContent = "+";

const decreaseLinkButton = document.createElement("button");
decreaseLinkButton.textContent = "-";

// Add buttons to the link resize popup
linkResizePopup.appendChild(increaseLinkButton);
linkResizePopup.appendChild(decreaseLinkButton);
document.body.appendChild(linkResizePopup);

// Event Listeners for Add Node popup
document.getElementById("add-node-btn").addEventListener("click", function() {
    document.getElementById("node-popup").style.display = "flex";
    // Clear form fields
    document.getElementById("node-label").value = "";
    document.getElementById("node-description").value = "";
    document.getElementById("node-shape").value = "circle";
    document.getElementById("node-color").value = "steelblue";
});

document.getElementById("add-node-cancel").addEventListener("click", function() {
    document.getElementById("node-popup").style.display = "none";
});

document.getElementById("add-node-confirm").addEventListener("click", function() {
    createNode();
    document.getElementById("node-popup").style.display = "none";
});

document.getElementById("link-mode-toggle").addEventListener("change", function() {
    isLinkMode = this.checked;
    document.getElementById("link-type-container").style.display = isLinkMode ? "block" : "none";
    
    if (!isLinkMode) {
        selectedSourceNode = null;
    }
});

document.getElementById("delete-mode-toggle").addEventListener("change", function() {
    isDeleteMode = this.checked;
});

document.getElementById("increase-size").addEventListener("click", function(event) {
    event.stopPropagation();
    console.log("Increase size clicked");
    if (selectedResizableNode) {
        console.log("Resizing node larger:", selectedResizableNode);
        const shape = selectedResizableNode.shape;
        if (shape === "circle") {
            const circle = d3.select(selectedResizableNode.element).select("circle");
            const newRadius = +circle.attr("r") + 5;
            circle.attr("r", newRadius);
        
            selectedResizableNode.data.size = newRadius;
        } else {
            const rect = d3.select(selectedResizableNode.element).select("rect");
            const newWidth = +rect.attr("width") + 5;
            const newHeight = +rect.attr("height") + 5;
            rect.attr("width", newWidth).attr("height", newHeight);
        
            selectedResizableNode.data.size = { width: newWidth, height: newHeight };
        }
    }
});

document.getElementById("decrease-size").addEventListener("click", function(event) {
    event.stopPropagation();
    console.log("Decrease size clicked");
    if (selectedResizableNode) {
        console.log("Resizing node smaller:", selectedResizableNode);
        const shape = selectedResizableNode.shape;
        if (shape === "circle") {
            const circle = d3.select(selectedResizableNode.element).select("circle");
            const newR = Math.max(10, +circle.attr("r") - 5);
            console.log("New circle radius:", newR);
            circle.attr("r", newR);
        } else {
            const rect = d3.select(selectedResizableNode.element).select("rect");
            const newW = Math.max(10, +rect.attr("width") - 5);
            const newH = Math.max(10, +rect.attr("height") - 5);
            console.log("New rectangle size:", newW, newH);
            rect.attr("width", newW).attr("height", newH);
        }
    }
});

// Add link resize button event listeners
increaseLinkButton.addEventListener("click", function(event) {
    event.stopPropagation();
    console.log("Increase link length clicked");
    if (selectedResizableLink) {
        const link = selectedResizableLink.link;
        link.distance = Math.min(300, link.distance + 20);
        console.log("New link distance:", link.distance);
        updateSimulationLinks();
    }
});

decreaseLinkButton.addEventListener("click", function(event) {
    event.stopPropagation();
    console.log("Decrease link length clicked");
    if (selectedResizableLink) {
        const link = selectedResizableLink.link;
        link.distance = Math.max(20, link.distance - 20);
        console.log("New link distance:", link.distance);
        updateSimulationLinks();
    }
});

function updateSimulationLinks() {
    simulation.force("link", d3.forceLink(links).distance(d => d.distance));
    simulation.alpha(0.3).restart();
}

document.addEventListener("click", function(event) {
    if (!resizePopup.contains(event.target)) {
        resizePopup.style.display = "none";
        selectedResizableNode = null;
    }
    if (!linkResizePopup.contains(event.target)) {
        linkResizePopup.style.display = "none";
        selectedResizableLink = null;
    }
});

document.getElementById("view-editors-btn").addEventListener("click", function() {
    const editorsList = document.getElementById("editors-list");
    if (editorsList) {
        if (editorsList.style.display === "none") {
            editorsList.style.display = "block";
        } else {
            editorsList.style.display = "none";
        }
    }
});

// Copy map ID
function copyMapId() {
    const mapIdElement = document.getElementById("display-map-id");
    const range = document.createRange();
    range.selectNode(mapIdElement);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    document.execCommand('copy');
    window.getSelection().removeAllRanges();
    alert('Map ID copied to clipboard!');
}

// SVG and simulation
const svg = d3.select("#map-container")
    .append("svg")
    .attr("width", "100%")
    .attr("height", "100%");
const svgGroup = svg.append("g");

const zoom = d3.zoom()
    .scaleExtent([0.5, 5])
    .on("zoom", event => svgGroup.attr("transform", event.transform));
svg.call(zoom);

// Define arrowhead marker
svg.append("defs").append("marker")
    .attr("id", "arrowhead")
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 15) // Reduced so it appears at the edge of the node
    .attr("refY", 0)
    .attr("markerWidth", 6)
    .attr("markerHeight", 6)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "black");

const simulation = d3.forceSimulation(nodes)
    .force("charge", d3.forceManyBody().strength(-30))
    .force("center", d3.forceCenter(window.innerWidth / 2, window.innerHeight / 2))
    .on("tick", ticked);

function updateVisualization() {
    const nodeElements = svgGroup.selectAll(".node").data(nodes, d => d.id);
    
    const nodeEnter = nodeElements.enter()
        .append("g")
        .attr("class", "node")
        .call(d3.drag()
            .on("start", dragstarted)
            .on("drag", dragged)
            .on("end", dragended));
    
    nodeEnter.on("click", function(event, node) {
        nodeClicked(event, node, this);
    });
    

    nodeEnter.each(function(d) {
        if (d.shape === "square") {
            const width = d.size?.width || 60;
            const height = d.size?.height || 60;
            d3.select(this).append("rect")
                .attr("x", -width / 2)
                .attr("y", -height / 2)
                .attr("width", width)
                .attr("height", height)
                .attr("fill", "white")
                .attr("stroke", d.color)
                .attr("stroke-width", 3);
        } else {
            const radius = d.size || 35;
            d3.select(this).append("circle")
                .attr("r", radius)
                .attr("fill", "white")
                .attr("stroke", d.color)
                .attr("stroke-width", 3); 
        }
    });

    nodeEnter.append("text")
    .attr("class", "node-label")
    .attr("text-anchor", "middle")
    .attr("dy", 0)
    .each(function(d) {
        const self = d3.select(this);
        const words = d.label.split(/\s+/).reverse();
        let word;
        let line = [];
        let lineNumber = 0;
        const lineHeight = 1.1; 
        const y = self.attr("y");
        const dy = parseFloat(self.attr("dy"));
        let tspan = self.append("tspan").attr("x", 0).attr("y", y).attr("dy", dy + "em");

        const maxWidth = d.shape === "square" 
            ? (d.size?.width || 60) * 0.8 
            : (d.size || 35) * 1.5;

        while (word = words.pop()) {
            line.push(word);
            tspan.text(line.join(" "));
            if (tspan.node().getComputedTextLength() > maxWidth) {
                line.pop();
                tspan.text(line.join(" "));
                line = [word];
                tspan = self.append("tspan")
                    .attr("x", 0)
                    .attr("y", y)
                    .attr("dy", ++lineNumber * lineHeight + dy + "em")
                    .text(word);
            }
        }
    });

    nodeEnter.append("title")
        .text(d => d.description);
    
    nodeElements.exit().remove();

    const linkElements = svgGroup.selectAll(".link").data(links);
    
    const linkEnter = linkElements.enter()
        .append("line")
        .attr("class", "link")
        .attr("stroke", "black")
        .attr("stroke-width", 2)
        .attr("marker-end", d => d.type === 'arrow' ? 'url(#arrowhead)' : null)
        .merge(linkElements)
        .attr("marker-end", d => d.type === 'arrow' ? 'url(#arrowhead)' : null);
    
    linkEnter.on("click", function(event, link) {
        linkClicked(event, link, this);
    });
    
    linkElements.exit().remove();



    simulation.nodes(nodes);
    updateSimulationLinks();
}

// Calculate intersection point of a line and a circle
function intersectCircleLine(cx, cy, r, x1, y1, x2, y2) {
    // Vector from line start to circle center
    const dx = x2 - x1;
    const dy = y2 - y1;
    
    // Calculate distance from point 1 to point 2
    const len = Math.sqrt(dx * dx + dy * dy);
    
    // Normalize the direction vector
    const nx = dx / len;
    const ny = dy / len;
    
    // Calculate the intersection point
    const intersectX = cx - r * nx;
    const intersectY = cy - r * ny;
    
    return { x: intersectX, y: intersectY };
}

function intersectRectLine(rx, ry, rw, rh, x1, y1, x2, y2) {
    const left = rx - rw / 2;
    const right = rx + rw / 2;
    const top = ry - rh / 2;
    const bottom = ry + rh / 2;
    
    const dx = x2 - x1;
    const dy = y2 - y1;
    
    const txMin = dx !== 0 ? (left - x1) / dx : Infinity;
    const txMax = dx !== 0 ? (right - x1) / dx : Infinity;
    const tyMin = dy !== 0 ? (top - y1) / dy : Infinity;
    const tyMax = dy !== 0 ? (bottom - y1) / dy : Infinity;
    
    const tMin = Math.max(Math.min(txMin, txMax), Math.min(tyMin, tyMax));
    const tMax = Math.min(Math.max(txMin, txMax), Math.max(tyMin, tyMax));
    
    if (tMin <= tMax && tMax >= 0) {
        const t = tMin >= 0 ? tMin : tMax;
        return {
            x: x1 + t * dx,
            y: y1 + t * dy
        };
    }
    
    return { x: rx, y: ry };
}

function getNodeShape(node) {
    const element = svgGroup.selectAll(".node").filter(d => d === node).node();
    if (!element) return null;
    
    if (node.shape === "square") {
        const rect = d3.select(element).select("rect");
        if (!rect.empty()) {
            return {
                type: "rect",
                width: +rect.attr("width"),
                height: +rect.attr("height")
            };
        }
    } else {
        const circle = d3.select(element).select("circle");
        if (!circle.empty()) {
            return {
                type: "circle",
                radius: +circle.attr("r")
            };
        }
    }
    return null;
}

function ticked() {
    svgGroup.selectAll(".node")
        .attr("transform", d => `translate(${d.x},${d.y})`);
    
    svgGroup.selectAll(".link").each(function(d) {
        const link = d3.select(this);
        
        const sourceShape = getNodeShape(d.source);
        const targetShape = getNodeShape(d.target);
        
        if (!sourceShape || !targetShape) return;
        
        const dx = d.target.x - d.source.x;
        const dy = d.target.y - d.source.y;
        
        let sourceX = d.source.x;
        let sourceY = d.source.y;
        
        let targetX = d.target.x;
        let targetY = d.target.y;
        
        if (sourceShape.type === "circle") {
            const intersection = intersectCircleLine(
                d.source.x, d.source.y, sourceShape.radius,
                d.target.x, d.target.y, d.source.x, d.source.y
            );
            sourceX = intersection.x;
            sourceY = intersection.y;
        } else if (sourceShape.type === "rect") {
            const intersection = intersectRectLine(
                d.source.x, d.source.y, 
                sourceShape.width, sourceShape.height,
                d.target.x, d.target.y, d.source.x, d.source.y
            );
            sourceX = intersection.x;
            sourceY = intersection.y;
        }
        
        if (targetShape.type === "circle") {
            const intersection = intersectCircleLine(
                d.target.x, d.target.y, targetShape.radius,
                d.source.x, d.source.y, d.target.x, d.target.y
            );
            targetX = intersection.x;
            targetY = intersection.y;
        } else if (targetShape.type === "rect") {
            const intersection = intersectRectLine(
                d.target.x, d.target.y, 
                targetShape.width, targetShape.height,
                d.source.x, d.source.y, d.target.x, d.target.y
            );
            targetX = intersection.x;
            targetY = intersection.y;
        }
        
        link.attr("x1", sourceX)
            .attr("y1", sourceY)
            .attr("x2", targetX)
            .attr("y2", targetY);
    });
}

function nodeClicked(event, node, element) {
    console.log("Node clicked:", node);
    console.log("isLinkMode:", isLinkMode, "isDeleteMode:", isDeleteMode);
    
    selectedResizableLink = null;
    
    if (isDeleteMode) {
        console.log("Deleting node:", node);
        nodes = nodes.filter(n => n !== node);
        const removedLinks = links.filter(l => l.source === node || l.target === node);
        links = links.filter(l => l.source !== node && l.target !== node);
        actionHistory.push({ type: 'delete-node', node, links: removedLinks });
        updateVisualization();
        return;
    }

    if (isLinkMode) {
        if (selectedSourceNode) {
            console.log("Creating link from", selectedSourceNode, "to", node);
            const type = document.getElementById('link-type').value;
            const newLink = { 
                source: selectedSourceNode, 
                target: node, 
                type, 
                distance: 100 
            };
            links.push(newLink);
            actionHistory.push({ type: 'add-link', link: newLink });
            selectedSourceNode = null;
            updateVisualization();
        } else {
            console.log("Selected source node:", node);
            selectedSourceNode = node;
        }
        return;
    }

    console.log("Showing resize popup for node:", node);
    selectedResizableNode = {
        element: element,
        shape: node.shape,
        data: node
    };
    
    // Position the resize popup near the node
    const rect = element.getBoundingClientRect();
    const bodyRect = document.body.getBoundingClientRect();
    
    const left = rect.left - bodyRect.left + window.scrollX + rect.width/2;
    const top = rect.top - bodyRect.top + window.scrollY + rect.height/2;
    
    console.log("Positioning popup at:", left, top);
    resizePopup.style.left = `${left}px`;
    resizePopup.style.top = `${top}px`;
    const descriptionDiv = document.getElementById("popup-description");
    descriptionDiv.textContent = node.description || "No description available";
    resizePopup.style.display = "block";
    event.stopPropagation();
}

function linkClicked(event, link, element) {
    console.log("Link clicked:", link);
    
    // Hide node resize popup first
    selectedResizableNode = null;
    
    // Don't show resize popup if in delete or link mode
    if (isDeleteMode) {
        console.log("Deleting link:", link);
        links = links.filter(l => l !== link);
        actionHistory.push({ type: 'delete-link', link });
        updateVisualization();
        return;
    }
    
    if (isLinkMode) {
        return;
    }
    
    console.log("Showing resize popup for link");
    selectedResizableLink = {
        element: element,
        link: link
    };
    
    // Position the link resize popup at the middle of the link
    const x1 = link.source.x;
    const y1 = link.source.y;
    const x2 = link.target.x;
    const y2 = link.target.y;
    
    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2;
    
    // Calculate screen position from SVG coordinates
    const svgRect = svg.node().getBoundingClientRect();
    const transform = d3.zoomTransform(svg.node());
    
    const screenX = svgRect.left + transform.applyX(midX);
    const screenY = svgRect.top + transform.applyY(midY);
    
    console.log("Positioning link popup at:", screenX, screenY);
    linkResizePopup.style.left = `${screenX}px`;
    linkResizePopup.style.top = `${screenY}px`;
    linkResizePopup.style.display = "block";

    // Stop event propagation
    event.stopPropagation();
}

function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

document.getElementById('undo-action').addEventListener('click', function() {
    const lastAction = actionHistory.pop();
    if (!lastAction) return;

    if (lastAction.type === 'add-node') {
        nodes = nodes.filter(n => n !== lastAction.node);
        links = links.filter(l => l.source !== lastAction.node && l.target !== lastAction.node);
    } else if (lastAction.type === 'delete-node') {
        nodes.push(lastAction.node);
        links.push(...lastAction.links);
    } else if (lastAction.type === 'delete-link') {
        links.push(lastAction.link);
    } else if (lastAction.type === 'add-link') {
        links = links.filter(l => l !== lastAction.link);
    }

    updateVisualization();
});

document.getElementById('zoom-in').addEventListener('click', function() {
    svg.transition().call(zoom.scaleBy, 1.2);
});

document.getElementById('zoom-out').addEventListener('click', function() {
    svg.transition().call(zoom.scaleBy, 0.8);
});

document.getElementById('save-map').addEventListener('click', function() {
    fetch('/save_map', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            mapId,
            nodes: nodes.map(n => {
                const element = d3.selectAll(".node").filter(d => d === n).node();
                let size = 35; // default for circles
                if (n.shape === "circle") {
                    const circle = d3.select(element).select("circle");
                    size = +circle.attr("r");
                } else {
                    const rect = d3.select(element).select("rect");
                    size = { width: +rect.attr("width"), height: +rect.attr("height") };
                }

                return {
                    label: n.label,
                    description: n.description,
                    x: n.x,
                    y: n.y,
                    shape: n.shape,
                    color: n.color,
                    size
                };
            }),
            
            links: links.map(l => ({
                sourceLabel: l.source.label,
                targetLabel: l.target.label,
                type: l.type || 'line',
                distance: l.distance || 100 
            }))
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            alert('Map saved successfully!');
        } else {
            alert('Error saving map: ' + data.message);
        }
    })
    .catch(err => {
        console.error(err);
        alert('Failed to save map');
    });
});

function createNode() {
    const label = document.getElementById('node-label').value.trim();
    const description = document.getElementById('node-description').value.trim();
    const shape = document.getElementById('node-shape').value;
    const color = document.getElementById('node-color').value;

    if (!label) {
        alert("Please enter a node label");
        return;
    }

    const newNode = {
        id: nodes.length,
        label,
        description,
        shape,
        color,
        x: window.innerWidth / 2,
        y: window.innerHeight / 2
    };

    nodes.push(newNode);
    actionHistory.push({ type: 'add-node', node: newNode });
    updateVisualization();

    document.getElementById('node-label').value = '';
    document.getElementById('node-description').value = '';
}

document.getElementById('back-to-maps-btn').addEventListener('click', function() {
    const confirmed = confirm("Have you saved your changes? Unsaved work will be lost. Proceed?");
    if (confirmed) {
        window.location.href = "/view_personal_maps";
    }
});

function renderAverageRating() {
    const container = document.getElementById("average-rating-stars");
    const rating = parseFloat(container.dataset.rating || 0);
    container.innerHTML = "";

    for (let i = 1; i <= 5; i++) {
        container.innerHTML += i <= rating ? "★" : "☆";
    }
}
renderAverageRating();

const rateButton = document.getElementById("rate-map-btn");
const ratingPopup = document.getElementById("rating-popup");

rateButton.addEventListener("click", () => {
    if (ratingPopup.style.display === "block") {
        ratingPopup.style.display = "none";
        return;
    }
    
    // Get button position for popup positioning
    const rect = rateButton.getBoundingClientRect();
    ratingPopup.style.left = `${rect.right + 10}px`; // Position to the right of the button
    ratingPopup.style.top = `${rect.top}px`; // Align with top of button
    ratingPopup.style.display = "block";
});

document.querySelectorAll("#rating-popup .star").forEach(star => {
    star.addEventListener("click", function () {
        const rating = this.dataset.value;
        fetch("/rate_map", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mapId, rating })
        }).then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                alert("Thanks for rating!");
                ratingPopup.style.display = "none";
                location.reload();
            }
        });
    });
});

// Render number of raters and toggle rater list
const ratingCountSpan = document.getElementById('rating-count');
const raterList = document.getElementById('rater-list');
const raterListItems = document.getElementById('rater-list-items');

ratingCountSpan.addEventListener('click', () => {
    const visible = raterList.style.display === 'block';
    raterList.style.display = visible ? 'none' : 'block';
});

// Populate rater list
const ratersData = JSON.parse(document.getElementById('average-rating-stars').getAttribute('data-raters') || "[]");
ratersData.forEach(rater => {
    const li = document.createElement('li');
    li.textContent = `${rater.username}: ${rater.rating} star${rater.rating !== 1 ? 's' : ''}`;
    raterListItems.appendChild(li);
});

updateVisualization();
console.log("Visualization initialized with", nodes.length, "nodes and", links.length, "links");
updateVisualization();