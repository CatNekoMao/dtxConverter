global UERelinkProjectDTXRollout

fn ueRelinkJoinPath a b =
(
    if (a == undefined or a == "") then
    (
        b
    )
    else
    (
        local lastChar = substring a a.count 1
        if (lastChar == "\\" or lastChar == "/") then (a + b) else (a + "\\" + b)
    )
)

fn ueRelinkNormalizePath p =
(
    if p == undefined then return ""
    local value = substituteString p "/" "\\"
    while (findString value "\\\\") != undefined do value = substituteString value "\\\\" "\\"
    value
)

fn ueRelinkDirectoryExists dirPath =
(
    (dotNetClass "System.IO.Directory").Exists dirPath
)

fn ueRelinkCollectFiles root pattern =
(
    local result = #()
    if (ueRelinkDirectoryExists root == false) then return result

    local dirs = #()
    local files = #()
    try (dirs = getDirectories (ueRelinkJoinPath root "*")) catch (dirs = #())
    try (files = getFiles (ueRelinkJoinPath root pattern)) catch (files = #())

    join result files
    for d in dirs do join result (ueRelinkCollectFiles d pattern)
    result
)

fn ueRelinkBuildDTXIndex projectDir =
(
    local index = dotNetObject "System.Collections.Hashtable"
    local duplicateCount = 0
    local files = ueRelinkCollectFiles projectDir "*.dtx"

    for f in files do
    (
        local key = toLower (getFilenameFile f)
        if (index.ContainsKey key) then
        (
            duplicateCount += 1
        )
        else
        (
            index.Add key (ueRelinkNormalizePath f)
        )
    )

    #(index, files.count, duplicateCount)
)

fn ueRelinkCollectRootMaterials =
(
    local result = #()

    for m in scenematerials do
    (
        if m != undefined and (findItem result m) == 0 do append result m
    )

    for obj in objects do
    (
        if obj.material != undefined and (findItem result obj.material) == 0 do append result obj.material
    )

    local meditCount = 0
    try (meditCount = meditMaterials.count) catch (meditCount = 0)
    for i = 1 to meditCount do
    (
        local mm = undefined
        try (mm = meditMaterials[i]) catch (mm = undefined)
        if mm != undefined and (findItem result mm) == 0 do append result mm
    )

    result
)

fn ueRelinkBitmapMapRecursive tex dtxIndex visited stats =
(
    if tex == undefined then return()

    local handle = 0
    try (handle = getHandleByAnim tex) catch (handle = 0)
    if handle != 0 and (findItem visited handle) > 0 then return()
    if handle != 0 do append visited handle

    if (isKindOf tex Bitmaptexture) then
    (
        stats[1] += 1

        local sourceName = ""
        try
        (
            if tex.filename != undefined and tex.filename != "" then
            (
                sourceName = getFilenameFile tex.filename
            )
        )
        catch()

        if (sourceName == "" and tex.name != undefined and tex.name != "") then
        (
            local cleanName = tex.name
            if (matchPattern cleanName pattern:"*.*") then cleanName = getFilenameFile cleanName
            sourceName = cleanName
        )

        local lookupKey = toLower sourceName
        local targetFile = undefined
        if lookupKey != "" and (dtxIndex.ContainsKey lookupKey) then
        (
            targetFile = dtxIndex.Item[lookupKey]
        )

        if targetFile != undefined and targetFile != "" then
        (
            local currentFile = ""
            try (currentFile = ueRelinkNormalizePath tex.filename) catch (currentFile = "")
            if currentFile != targetFile then
            (
                try
                (
                    tex.filename = targetFile
                    stats[2] += 1
                )
                catch
                (
                    stats[4] += 1
                )
            )
        )
        else
        (
            stats[3] += 1
        )
    )

    local subCount = 0
    try (subCount = getNumSubTexmaps tex) catch (subCount = 0)
    for i = 1 to subCount do
    (
        local subTex = undefined
        try (subTex = getSubTexmap tex i) catch (subTex = undefined)
        ueRelinkBitmapMapRecursive subTex dtxIndex visited stats
    )
)

fn ueRelinkMaterialRecursive mat dtxIndex visited stats =
(
    if mat == undefined then return()

    local handle = 0
    try (handle = getHandleByAnim mat) catch (handle = 0)
    if handle != 0 and (findItem visited handle) > 0 then return()
    if handle != 0 do append visited handle

    local subTexCount = 0
    try (subTexCount = getNumSubTexmaps mat) catch (subTexCount = 0)
    for i = 1 to subTexCount do
    (
        local tex = undefined
        try (tex = getSubTexmap mat i) catch (tex = undefined)
        ueRelinkBitmapMapRecursive tex dtxIndex visited stats
    )

    local subMtlCount = 0
    try (subMtlCount = getNumSubMtls mat) catch (subMtlCount = 0)
    for i = 1 to subMtlCount do
    (
        local subMat = undefined
        try (subMat = getSubMtl mat i) catch (subMat = undefined)
        ueRelinkMaterialRecursive subMat dtxIndex visited stats
    )
)

fn ueRelinkEnvironmentMap environmentTex dtxIndex visited stats =
(
    if environmentTex == undefined then return()
    ueRelinkBitmapMapRecursive environmentTex dtxIndex visited stats
)

fn ueRelinkSceneTexturesToProjectDTX projectDir =
(
    local normalizedDir = ueRelinkNormalizePath projectDir
    if normalizedDir == "" then
    (
        messageBox "Enter a project texture folder first." title:"Relink Project DTX"
        return false
    )

    if (ueRelinkDirectoryExists normalizedDir == false) then
    (
        messageBox ("Folder does not exist:\n" + normalizedDir) title:"Relink Project DTX"
        return false
    )

    local buildResult = ueRelinkBuildDTXIndex normalizedDir
    local dtxIndex = buildResult[1]
    local indexedCount = buildResult[2]
    local duplicateCount = buildResult[3]

    if indexedCount == 0 then
    (
        messageBox ("No .dtx files were found under:\n" + normalizedDir) title:"Relink Project DTX"
        return false
    )

    local visited = #()
    local stats = #(0, 0, 0, 0)
    local materials = ueRelinkCollectRootMaterials()

    for m in materials do ueRelinkMaterialRecursive m dtxIndex visited stats

    local envMap = undefined
    try (envMap = environmentMap) catch (envMap = undefined)
    ueRelinkEnvironmentMap envMap dtxIndex visited stats

    try (updateMTLInMedit()) catch()
    try (redrawViews()) catch()

    local msg = ""
    msg += ("Project folder:\n" + normalizedDir + "\n\n")
    msg += ("Indexed DTX files: " + indexedCount as string + "\n")
    msg += ("Duplicate DTX names skipped: " + duplicateCount as string + "\n")
    msg += ("Bitmap textures visited: " + stats[1] as string + "\n")
    msg += ("Replaced: " + stats[2] as string + "\n")
    msg += ("No matching DTX: " + stats[3] as string + "\n")
    msg += ("Replace failed: " + stats[4] as string)

    messageBox msg title:"Relink Project DTX"
    true
)

try (destroyDialog UERelinkProjectDTXRollout) catch()

rollout UERelinkProjectDTXRollout "Relink Scene Textures To Project DTX" width:520 height:136
(
    label lblInfo "Choose or enter a project texture folder. The script will relink scene bitmap textures to same-name .dtx files under that folder." pos:[12,10] width:492 height:32
    editText edtProjectDir "" pos:[12,44] width:392 height:20
    button btnBrowse "Browse..." pos:[412,42] width:96 height:24
    button btnRun "Relink" pos:[12,84] width:496 height:28

    on btnBrowse pressed do
    (
        local picked = getSavePath caption:"Pick project texture folder"
        if picked != undefined do edtProjectDir.text = ueRelinkNormalizePath picked
    )

    on btnRun pressed do
    (
        ueRelinkSceneTexturesToProjectDTX edtProjectDir.text
    )
)

createDialog UERelinkProjectDTXRollout style:#(#style_titlebar, #style_sysmenu, #style_toolwindow)
